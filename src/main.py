import asyncio
import os
from distutils import util

import cv2
import numpy as np
import supervisely as sly
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from supervisely.app.v1.app_service import AppService
from supervisely.geometry.constants import BITMAP
from supervisely.imaging.color import generate_rgb
from supervisely.video.sampling import async_stream_video_frames
from supervisely.video_annotation.key_id_map import KeyIdMap

if sly.is_development():
    load_dotenv("debug.env")
    load_dotenv("/home/serpntns/supervisely.env")

TEAM_ID = sly.env.team_id()
WORKSPACE_ID = sly.env.workspace_id()
VIDEO_ID = os.environ.get("modal.state.videoId", "")
ALL_FRAMES = bool(util.strtobool(os.environ.get("modal.state.allFrames", "True")))
START_FRAME = int(os.environ.get("modal.state.startFrame", 0))
END_FRAME = int(os.environ.get("modal.state.endFrame", 0))
SHOW_NAMES = bool(util.strtobool(os.environ.get("modal.state.showClassName", "True")))
THICKNESS = int(os.environ.get("modal.state.thickness", 3))
OPACITY = float(os.environ.get("modal.state.opacity", 50)) / 100.0
POINT_RADIUS = int(os.environ.get("modal.state.pointRadius", 5))

my_app: AppService = AppService()

PROJECT_ID = None
CLASSES = []
COLOR_INS = True
FONT = cv2.FONT_HERSHEY_COMPLEX
FONT_PATH = "fonts/FiraSans-Bold.ttf"
absolute_font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), FONT_PATH)
font_size = 32
DEFAULT_FPS = 25.0


def _resolve_frame_duration_sec(video_info, app_logger):
    # video_info.frames_to_timecodes (fileMeta.framesToTimecodes) isn't always populated by the
    # server - fall back to an average frame duration derived from duration/frames_count, and
    # only as a last resort to a hardcoded default.
    frames_to_timecodes = video_info.frames_to_timecodes
    if frames_to_timecodes and len(frames_to_timecodes) > 1:
        return frames_to_timecodes[1]

    duration = (video_info.file_meta or {}).get("duration")
    if duration and video_info.frames_count:
        return duration / video_info.frames_count

    app_logger.warn(
        "Could not determine fps for video {!r} (id={}) from its metadata; "
        "falling back to {} fps.".format(video_info.name, video_info.id, DEFAULT_FPS)
    )
    return 1 / DEFAULT_FPS


def _iterate_frames_sync(api, video_id, start, end):
    """Bridges the async `async_stream_video_frames` generator into a sync iterator, since this
    app's callback runs synchronously. Demuxes/decodes the video directly (PyAV) instead of one
    HTTP round-trip per frame.

    Callers MUST consume this via a `try/finally: frame_iter.close()` (or exhaust it fully) -
    if the consuming loop exits early via an exception, nothing else closes the underlying
    async generator, leaking its decode thread/executor for the life of the process.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "_iterate_frames_sync must be called from a thread with no running event loop."
        )

    loop = asyncio.new_event_loop()
    agen = async_stream_video_frames(api, video_id, start=start, end=end)
    try:
        while True:
            try:
                yield loop.run_until_complete(agen.__anext__())
            except StopAsyncIteration:
                break
    finally:
        loop.run_until_complete(agen.aclose())
        loop.close()


@my_app.callback("render_video_labels_to_mp4")
@sly.timeit
def render_video_labels_to_mp4(api: sly.Api, task_id, context, state, app_logger):
    global VIDEO_ID, START_FRAME, END_FRAME, PROJECT_ID
    original_video_id = VIDEO_ID
    if VIDEO_ID == "":
        raise ValueError(
            "Please, copy Video ID from your project and paste it to the modal window."
        )
    VIDEO_ID = "".join(filter(str.isnumeric, VIDEO_ID))
    if not VIDEO_ID.isnumeric():
        raise ValueError(
            f"Invalid Video ID: {original_video_id}. "
            "Please, copy Video ID from your project and paste it to the modal window."
        )
    VIDEO_ID = int(VIDEO_ID)
    video_info = api.video.get_info_by_id(VIDEO_ID)
    if video_info is None:
        raise ValueError(
            f"Video with id={original_video_id} not found. Please, copy Video ID from your project and paste it to the modal window."
        )
    PROJECT_ID = video_info.project_id
    project_info = api.project.get_info_by_id(PROJECT_ID)
    if project_info.workspace_id != WORKSPACE_ID:
        raise ValueError(
            "Video is not in current workspace. "
            "Please, copy Video ID from the project in current workspace."
        )
    if ALL_FRAMES is True:
        START_FRAME = 0
        END_FRAME = video_info.frames_count - 1
    else:
        if START_FRAME == 0 and END_FRAME == 0:
            raise ValueError("Frame Range is not defined")
        if END_FRAME >= video_info.frames_count:
            app_logger.warn(
                "End Frame {} is out of range: video has only {} frames".format(
                    END_FRAME, video_info.frames_count
                )
            )
            END_FRAME = video_info.frames_count - 1
            app_logger.warn("End Frame has been set to {}".format(END_FRAME))

    frame_per_second = _resolve_frame_duration_sec(video_info, app_logger)
    stream_speed = 1 / frame_per_second

    meta_json = api.project.get_meta(PROJECT_ID)
    meta = sly.ProjectMeta.from_json(meta_json)
    key_id_map = KeyIdMap()
    if len(meta.obj_classes) == 0:
        raise ValueError("No classes in project")

    ann_info = api.video.annotation.download(VIDEO_ID)
    ann = sly.VideoAnnotation.from_json(ann_info, meta, key_id_map)

    obj_to_color = {}
    exist_colors = []
    video = None
    font = ImageFont.truetype(absolute_font_path, font_size)

    mp4_name = sly.fs.get_file_name(video_info.name) + ".mp4"
    local_path = os.path.join(my_app.data_dir, mp4_name)
    progress = sly.Progress(video_info.name, END_FRAME - START_FRAME + 1)
    # last_frame is the original range(START_FRAME, END_FRAME)'s (exclusive-end) last index,
    # translated for async_stream_video_frames' inclusive `end`. If the range is empty (or
    # inverted), skip streaming entirely instead of calling in with end < start - that function
    # clamps end up to start and would yield 1 frame instead of the 0 frames this app expects
    # (falls through to "No frames to create video" below, same as the original code).
    last_frame = END_FRAME - 1
    frame_iter = (
        _iterate_frames_sync(api, VIDEO_ID, START_FRAME, last_frame)
        if last_frame >= START_FRAME
        else (x for x in ())  # empty generator - also supports .close(), unlike iter(())
    )
    try:
        for frame_number, frame_np in frame_iter:
            ann_frame = ann.frames.get(frame_number, None)
            if ann_frame is not None:
                for fig in ann_frame.figures:
                    if len(CLASSES) == 0 or fig.video_object.obj_class.name in CLASSES:
                        color = fig.video_object.obj_class.color

                        if COLOR_INS:
                            if fig.video_object.key not in obj_to_color:
                                color = generate_rgb(exist_colors)
                                obj_to_color[fig.video_object.key] = color
                                exist_colors.append(color)
                            else:
                                color = obj_to_color[fig.video_object.key]

                        bbox = None
                        if (
                            fig.geometry.geometry_name() == BITMAP
                            or fig.geometry.geometry_name() == "polygon"
                        ):
                            mask = np.zeros(frame_np.shape, dtype=np.uint8)
                            fig.geometry.draw(mask, color)
                            frame_np = cv2.addWeighted(frame_np, 1, mask, OPACITY, 0)
                            if SHOW_NAMES == True:
                                bbox = fig.geometry.to_bbox()
                                bbox.draw_contour(frame_np, color, THICKNESS)

                        elif fig.geometry.geometry_name() == "rectangle":
                            bbox = fig.geometry
                            bbox.draw_contour(frame_np, color, THICKNESS)

                        elif fig.geometry.geometry_name() in ["point", "line"]:
                            bbox = fig.geometry.to_bbox()
                            if fig.geometry.geometry_name() == "point":
                                fig.geometry.draw(frame_np, color, thickness=POINT_RADIUS)
                            else:
                                fig.geometry.draw(frame_np, color, thickness=THICKNESS)

                        else:
                            raise TypeError(
                                "Geometry type {} not supported".format(
                                    fig.geometry.geometry_name()
                                )
                            )

                        if SHOW_NAMES == True:
                            # tl = 1  # line/font thickness
                            # c1, c2 = (bbox.left, bbox.top), (bbox.right, bbox.bottom)
                            # tf = 1  # font thickness
                            # t_size = cv2.getTextSize(
                            #     fig.video_object.obj_class.name, FONT, fontScale=tl, thickness=tf
                            # )[0]
                            # c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3

                            # cv2.rectangle(
                            #     frame_np, c1, c2, fig.video_object.obj_class.color, -1, cv2.LINE_AA
                            # )  # filled

                            # cv2.putText(
                            #     frame_np,
                            #     fig.video_object.obj_class.name,
                            #     (bbox.left + 1, bbox.top - 1),
                            #     cv2.FONT_HERSHEY_SIMPLEX,
                            #     1,
                            #     [255, 255, 255],
                            #     thickness=THICKNESS,
                            #     lineType=cv2.LINE_AA,
                            #     bottomLeftOrigin=False,
                            # )

                            image_pil = Image.fromarray(cv2.cvtColor(frame_np, cv2.COLOR_BGR2RGB))
                            draw = ImageDraw.Draw(image_pil)
                            text = fig.video_object.obj_class.name
                            text_color = (79, 79, 79)
                            t_bbox = draw.textbbox((0, 0), text, font=font)
                            t_width = t_bbox[2] - t_bbox[0]
                            t_height = t_bbox[3] - t_bbox[1]
                            padding_x = 10
                            padding_y = 5
                            c1 = (bbox.left, bbox.top - t_height - 2 * padding_y)
                            c2 = (
                                c1[0] + t_width + 2 * padding_x,
                                c1[1] + t_height + 2 * padding_y,
                            )
                            position = (bbox.left + padding_x, bbox.top - t_height - padding_y)
                            rect_color = (color[2], color[1], color[0])
                            draw.rectangle([c1, c2], fill=rect_color)
                            draw.text(position, text, font=font, fill=text_color)
                            frame_np = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)

            if video is None:
                video = cv2.VideoWriter(
                    local_path,
                    cv2.VideoWriter_fourcc(*"MP4V"),
                    stream_speed,
                    (frame_np.shape[1], frame_np.shape[0]),
                )

            frame_np = cv2.cvtColor(frame_np, cv2.COLOR_BGR2RGB)
            video.write(frame_np)
            progress.iter_done_report()
    finally:
        frame_iter.close()

    if video is None:
        raise ValueError("No frames to create video")
    video.release()

    remote_path = os.path.join(
        sly.team_files.RECOMMENDED_EXPORT_PATH,
        "rendered_videos",
        "{}_{}".format(VIDEO_ID, mp4_name),
    )
    remote_path = api.file.get_free_name(TEAM_ID, remote_path)
    upload_progress = []

    def _print_progress(monitor, upload_progress):
        if len(upload_progress) == 0:
            upload_progress.append(
                sly.Progress(
                    message="Upload {!r}".format(mp4_name),
                    total_cnt=monitor.len,
                    ext_logger=app_logger,
                    is_size=True,
                )
            )
        upload_progress[0].set_current_value(monitor.bytes_read)

    file_info = api.file.upload(
        TEAM_ID, local_path, remote_path, lambda m: _print_progress(m, upload_progress)
    )
    app_logger.info("Uploaded to Team-Files: {!r}".format(remote_path))
    api.task._set_custom_output(
        task_id,
        file_info.id,
        file_info.name,
        file_url=file_info.storage_path,
        description=f"File mp4: {remote_path}",
        icon="zmdi zmdi-cloud-download",
        download=True,
    )
    sly.fs.silent_remove(local_path)
    my_app.stop()


def main():
    sly.logger.info(
        "Script arguments",
        extra={
            "TEAM_ID": TEAM_ID,
            "WORKSPACE_ID": WORKSPACE_ID,
            "VIDEO_ID": VIDEO_ID,
            "ALL_FRAMES": ALL_FRAMES,
            "START_FRAME": START_FRAME,
            "END_FRAME": END_FRAME,
            "SHOW_NAMES": SHOW_NAMES,
            "THICKNESS": THICKNESS,
            "OPACITY": OPACITY,
        },
    )
    my_app.run(initial_events=[{"command": "render_video_labels_to_mp4"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main, log_for_agent=False)
