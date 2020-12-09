import os
from distutils import util
import cv2
import numpy as np

import supervisely_lib as sly
from supervisely_lib.video_annotation.key_id_map import KeyIdMap
from supervisely_lib.geometry.constants import BITMAP
from supervisely_lib.imaging.color import generate_rgb

TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
VIDEO_ID = os.environ['modal.state.videoId']
ALL_FRAMES = bool(util.strtobool(os.environ['modal.state.allFrames']))
START_FRAME = int(os.environ['modal.state.startFrame'])
END_FRAME = int(os.environ['modal.state.endFrame'])
SHOW_NAMES = bool(util.strtobool(os.environ['modal.state.showClassName']))
THICKNESS = int(os.environ['modal.state.thickness'])
OPACITY = float(os.environ['modal.state.opacity'])

my_app = sly.AppService()

PROJECT_ID = None
CLASSES = []
COLOR_INS = True
FONT = cv2.FONT_HERSHEY_COMPLEX


@my_app.callback("render_video_labels_to_mp4")
@sly.timeit
def render_video_labels_to_mp4(api: sly.Api, task_id, context, state, app_logger):
    global VIDEO_ID, START_FRAME, END_FRAME, PROJECT_ID
    if VIDEO_ID == "":
        raise ValueError("Video ID is not defined")
    VIDEO_ID = int(VIDEO_ID)
    video_info = api.video.get_info_by_id(VIDEO_ID)
    if video_info is None:
        raise ValueError("Video with id={!r} not found".format(VIDEO_ID))
    PROJECT_ID = video_info.project_id
    if ALL_FRAMES is True:
        START_FRAME = 0
        END_FRAME = video_info.frames_count - 1
    else:
        if START_FRAME == 0 and END_FRAME == 0:
            raise ValueError("Frame Range is not defined")
        if END_FRAME >= video_info.frames_count:
            app_logger.warn("End Frame {} is out of range: video has only {} frames"
                            .format(END_FRAME, video_info.frames_count))
            END_FRAME = video_info.frames_count - 1
            app_logger.warn("End Frame has been set to {}".format(END_FRAME))

    frame_per_second = video_info.frames_to_timecodes[1]
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
    local_path = os.path.join(my_app.data_dir, video_info.name)
    progress = sly.Progress(video_info.name, END_FRAME - START_FRAME + 1)
    for frame_number in range(START_FRAME, END_FRAME):
        frame_np = api.video.frame.download_np(VIDEO_ID, frame_number)
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
                    if fig.geometry.geometry_name() == BITMAP or fig.geometry.geometry_name() == 'polygon':
                        mask = np.zeros(frame_np.shape, dtype=np.uint8)
                        fig.geometry.draw(mask, color)
                        frame_np = cv2.addWeighted(frame_np, 1, mask, OPACITY, 0)
                        if SHOW_NAMES == True:
                           bbox = fig.geometry.to_bbox()
                           bbox.draw_contour(frame_np, color, THICKNESS)

                    elif fig.geometry.geometry_name() == 'rectangle':
                        bbox = fig.geometry
                        bbox.draw_contour(frame_np, color, THICKNESS)

                    if SHOW_NAMES == True:
                        tl = 1  # line/font thickness
                        c1, c2 = (bbox.left, bbox.top), (bbox.right, bbox.bottom)
                        tf = 1  # font thickness
                        t_size = cv2.getTextSize(fig.video_object.obj_class.name, FONT, fontScale=tl, thickness=tf)[0]
                        c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3

                        cv2.rectangle(frame_np, c1, c2, fig.video_object.obj_class.color, -1, cv2.LINE_AA)  # filled

                        cv2.putText(frame_np, fig.video_object.obj_class.name, (bbox.left + 1, bbox.top - 1),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1,
                                    [255, 255, 255],
                                    thickness=THICKNESS, lineType=cv2.LINE_AA, bottomLeftOrigin=False)
                    else:
                        raise TypeError("Geometry type {} not supported".format(fig.geometry.geometry_name()))

        if video is None:
            video = cv2.VideoWriter(local_path,
                                    cv2.VideoWriter_fourcc(*'MP4V'),
                                    stream_speed,
                                    (frame_np.shape[1], frame_np.shape[0]))

        frame_np = cv2.cvtColor(frame_np, cv2.COLOR_BGR2RGB)
        video.write(frame_np)
        progress.iter_done_report()

    if video is None:
        raise ValueError('No frames to create video')
    video.release()

    print(sly.fs.list_dir_recursively(my_app.data_dir))

    remote_path = os.path.join('/rendered_videos', "{}_{}".format(VIDEO_ID, video_info.name))
    remote_path = api.file.get_free_name(TEAM_ID, remote_path)

    upload_progress = []
    def _print_progress(monitor, upload_progress):
        if len(upload_progress) == 0:
            upload_progress.append(sly.Progress(message="Upload {!r}".format(video_info.name),
                                                total_cnt=monitor.len,
                                                ext_logger=app_logger,
                                                is_size=True))
        upload_progress[0].set_current_value(monitor.bytes_read)

    print("exists", sly.fs.file_exists(local_path))
    file_info = api.file.upload(TEAM_ID, local_path, remote_path, lambda m: _print_progress(m, upload_progress))
    app_logger.info("Uploaded to Team-Files: {!r}".format(remote_path))
    api.task._set_custom_output(task_id, file_info.id, file_info.name,
                                description="File mp4", icon="zmdi zmdi-cloud-download")
    sly.fs.silent_remove(local_path)
    my_app.stop()


def main():
    sly.logger.info("Script arguments", extra={
        "TEAM_ID": TEAM_ID,
        "WORKSPACE_ID": WORKSPACE_ID,
        "VIDEO_ID": VIDEO_ID,
        "ALL_FRAMES": ALL_FRAMES,
        "START_FRAME": START_FRAME,
        "END_FRAME": END_FRAME,
        "SHOW_NAMES": SHOW_NAMES,
        "THICKNESS": THICKNESS,
        "OPACITY": OPACITY
    })
    my_app.run(initial_events=[{"command": "render_video_labels_to_mp4"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)