<div align="center" markdown>
<img src="https://i.imgur.com/4hmKT5z.png"/>

# Render Video Labels to MP4

<p align="center">
  <a href="#Overview">Overview</a> •
  <a href="#How-To-Use">How To Use</a>
</p>


[![](https://img.shields.io/badge/supervisely-ecosystem-brightgreen)](https://ecosystem.supervise.ly/apps/render-video-labels-to-mp4)
[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervise.ly/slack)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/render-video-labels-to-mp4)
[![views](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/render-video-labels-to-mp4&counter=views&label=views)](https://supervise.ly)
[![used by teams](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/render-video-labels-to-mp4&counter=downloads&label=used%20by%20teams)](https://supervise.ly)
[![runs](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/render-video-labels-to-mp4&counter=runs&label=runs)](https://supervise.ly)

</div>

## Overview

Creates presentation mp4 file based on labeled video. Object instances are always rendered with random colors. It helps to distinguish objects of the same class on the frame. Class name is rendered with original class color. 

Example of the results:
Example: bitmap with opacity  |  Example: rectangles
:-------------------------:|:-----------------------------------:
[![Watch the video](https://i.imgur.com/MlKpFop.png)](https://youtu.be/htUaZ8su_M0)  |  [![Watch the video](https://i.imgur.com/aNwT5Tr.png)](https://youtu.be/DQnkGpM-ivM)


## How To Use

**Step 1:** Add app to your team from Ecosystem if it is not there

**Step 2:** Copy to clipboard id of the video that should be rendered with labels

<img src="https://i.imgur.com/DssYeoe.png"/>

**Step 2:** Run app from team apps page: 

<img src="https://i.imgur.com/dmXj7K3.png"/>

**Step 3:** Define input arguments in modal window: `video id`, `line width`, `opacity` for bitmap objects, `frame range`, etc.. and press `Run` button

<img src="https://i.imgur.com/7Zx57yP.png" width="450px"/>

**Step 4:** Wait until task is finished. Result video is saved to `Team Files` to directory: `/rendered_videos/` with name `<video-id>_<video-name>.mp4`. 

File can be download directly from team files (right click on the file -> `Download`) 

<img src="https://i.imgur.com/NwZ3AMK.png"/>

or from workspace tasks list by clicking on the download URL in task output column

<img src="https://i.imgur.com/VJwrmpH.png"/>

