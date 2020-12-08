import supervisely_lib as sly
from supervisely_lib.video_annotation.key_id_map import KeyIdMap
import cv2
import numpy as np
from supervisely_lib.geometry.constants import BITMAP
from supervisely_lib.imaging.color import generate_rgb

my_app = sly.AppService()

PROJECT_ID = 1414
TEAM_ID = 8
VIDEO_ID = 375956 #animal
#VIDEO_ID = 375957 #cars
START_FRAME = 50
END_FRAME = 200
CLASSES = []
COLOR_INS = True
THICKNESS = 3
SHOW_NAMES = True #for bitmap and bbox

FONT = cv2.FONT_HERSHEY_COMPLEX
OPACITY = 0.5
OUTPUT_VIDEO_NAME = "del_me_test_name_bbox_1070_animal.mp4"

VIDEO_NAME = 'Videos_dataset_cars_cars.mp4'
APP_DIR = my_app.data_dir + "/"
#Videos_dataset_animals_sea_lion.mp4
#Videos_dataset_cars_cars.mp4

api = sly.Api.from_env()
video_info = api.video.get_info_by_id(VIDEO_ID)
frame_per_second = video_info.frames_to_timecodes[1]
STREAM_SPEED = 1 / frame_per_second


@my_app.callback("render_video_labels_to_mp4")
@sly.timeit
def render_video_labels_to_mp4(api: sly.Api, task_id, context, state, app_logger):
    meta_json = api.project.get_meta(PROJECT_ID)
    meta = sly.ProjectMeta.from_json(meta_json)
    key_id_map = KeyIdMap()

    if video_info is None:
        raise RuntimeError("Video with id={!r} not found".format(VIDEO_ID))

    if len(meta.obj_classes) == 0:
        raise ValueError("No classses in project")

    ann_info = api.video.annotation.download(VIDEO_ID)
    ann = sly.VideoAnnotation.from_json(ann_info, meta, key_id_map)

    # if END_FRAME is None or START_FRAME is None:
    #     START_FRAME = 0
    #     END_FRAME = ann.frames_count - 1
    #
    # if END_FRAME >= ann.frames_count:
    #     raise ValueError("Frame: {!r} not found".format(END_FRAME))

    frames_with_classes = []
    fig_to_color = {}
    exist_colors = []
    for frame_number in range(START_FRAME, END_FRAME):
        frame_np = api.video.frame.download_np(VIDEO_ID, frame_number)
        ann_frame = ann.frames.get(frame_number)

        for fig in ann_frame.figures:
            if len(CLASSES) == 0 or fig.video_object.obj_class.name in CLASSES:
                if COLOR_INS:
                    if fig.video_object.key not in fig_to_color:
                        color = generate_rgb(exist_colors)
                        fig_to_color[fig.video_object.key] = color
                        exist_colors.append(color)
                    else:
                        color = fig_to_color[fig.video_object.key]
                else:
                    color = fig.video_object.obj_class.color

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

                    tl = round(0.002 * (frame_np.shape[0] + frame_np.shape[1]) / 2) + 1  # line/font thickness
                    c1, c2 = (int(bbox.left), int(bbox.top)), (int(bbox.right), int(bbox.bottom))
                    tf = max(tl - 1, 1)  # font thickness
                    t_size = cv2.getTextSize(fig.video_object.obj_class.name, 0, fontScale=tl / 3, thickness=tf)[0]
                    c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3

                    cv2.rectangle(frame_np, c1, c2, fig.video_object.obj_class.color, -1, cv2.LINE_AA)  # filled

                    cv2.putText(frame_np, fig.video_object.obj_class.name, (bbox.left + 10, bbox.top - 7),
                                cv2.FONT_HERSHEY_SIMPLEX, 1,
                                [255, 255, 255],
                                thickness=THICKNESS, lineType=cv2.LINE_AA, bottomLeftOrigin=False)
                else:
                    raise TypeError("Geometry type {} not supported".format(fig.geometry.geometry_name()))

        frames_with_classes.append(frame_np)


    if len(frames_with_classes) == 0:
        raise ValueError('No frames to create video')

    height, width, layers = frames_with_classes[0].shape
    video = cv2.VideoWriter(VIDEO_NAME, cv2.VideoWriter_fourcc(*'MP4V'), STREAM_SPEED, (width, height))

    for image in frames_with_classes:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        video.write(image)

    video.release()

    upload_progress = []

    def _print_progress(monitor, upload_progress):
        if len(upload_progress) == 0:
            upload_progress.append(sly.Progress(message="Upload {!r}".format(VIDEO_NAME),
                                                total_cnt=monitor.len,
                                                ext_logger=app_logger,
                                                is_size=True))
        upload_progress[0].set_current_value(monitor.bytes_read)

    file_info = api.file.upload(TEAM_ID, VIDEO_NAME, OUTPUT_VIDEO_NAME, lambda m: _print_progress(m, upload_progress))
    app_logger.info("Uploaded to Team-Files: {!r}".format(file_info.full_storage_url))

    my_app.stop()


def main():
    sly.logger.info("Script arguments", extra={
        "PROJECT_ID": PROJECT_ID,
        "VIDEO_ID": VIDEO_ID,
#        "START_FRAME": START_FRAME,
#        "END_FRAME": END_FRAME
#        "context.projectId": PROJECT_ID,
#        "context.videoId": VIDEO_ID
    })

    my_app.run(initial_events=[{"command": "render_video_labels_to_mp4"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)