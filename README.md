<div align="center" markdown>
<img src="media/poster.png"/>

# Render Video Labels to MP4

<p align="center">
  <a href="#Overview">Overview</a> •
  <a href="#How-To-Use">How To Use</a>
</p>


[![](https://img.shields.io/badge/supervisely-ecosystem-brightgreen)](https://ecosystem.supervise.ly/apps/render-video-labels-to-mp4)
[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervise.ly/slack)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/render-video-labels-to-mp4)
[![views](https://app.supervise.ly/img/badges/views/supervisely-ecosystem/render-video-labels-to-mp4.png)](https://supervise.ly)
[![runs](https://app.supervise.ly/img/badges/runs/supervisely-ecosystem/render-video-labels-to-mp4.png)](https://supervise.ly)

</div>

## Overview

Creates presentation mp4 file based on labeled video. Object instances are always rendered with random colors. It helps to distinguish objects of the same class on the frame. Class name is rendered with original class color. 

Example of the results:
Example: bitmap with opacity  |  Example: rectangles
:-------------------------:|:-----------------------------------:
[![Watch the video](media/ov1.png)](https://youtu.be/htUaZ8su_M0)  |  [![Watch the video](media/ov2.png)](https://youtu.be/DQnkGpM-ivM)


## How To Use

**Step 1:** Add app to your team from Ecosystem if it is not there

**Step 2:** Copy to clipboard id of the video that should be rendered with labels

<img src="media/htu2.png"/>

**Step 2:** Run app from team apps page: 

<img src="media/htu2a.png"/>

**Step 3:** Define input arguments in modal window: `video id`, `line width`, `opacity` for bitmap objects, `frame range`, etc.. and press `Run` button

<img src="media/htu3.png" width="450px"/>

**Step 4:** Wait until task is finished. Result video is saved to `Team Files` to directory: `/rendered_videos/` with name `<video-id>_<video-name>.mp4`. 

File can be download directly from team files (right click on the file -> `Download`) 

<img src="media/htu4.png"/>

or from workspace tasks list by clicking on the download URL in task output column

<img src="media/htu4a.png"/>

