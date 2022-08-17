import os
import subprocess


videos = {}
timeline = []


def read_video_info(line):
    video_name = line.split(";")[0].strip()
    ref_frame = line.split(";")[1].strip()
    vid_path = line.split(";")[2].strip()
    videos[video_name] = (ref_frame, vid_path)


def read_extra_settings(settings_list):
    # this is used to read the extra config in the timeline (frame #, center, and resolution)
    info = settings_list.split(",")
    frame = info[0].strip().translate({ord(x): '' for x in ['[', ']', ';']})
    if len(info) == 3:
        center = info[1].strip().translate({ord(x): '' for x in ['[', ']', ';']})
        resolution = info[2].strip().translate({ord(x): '' for x in ['[', ']', ';']})
        return {"Frame": frame, "Center": center, "Resolution": resolution}
    else:
        return {"Frame": frame}


def read_timeline_info(line):
    video_name = line.split(";")[1].strip()
    speed = line.split(";")[2].strip()
    start_settings = line.split("[")[1]
    stop_settings = line.split("[")[-1]

    start_config = read_extra_settings(start_settings)
    end_config = read_extra_settings(stop_settings)

    timeline.append({"Video": video_name, "Speed": speed, "StartConfig": start_config, "EndConfig": end_config})


def read_config(config_file):
    # this function is used to process the first part of the config file
    for line in config_file:
        if line.startswith("video"):
            read_video_info(line)
        elif line.startswith("timeline"):
            read_timeline_info(line)


def read_txt(config_path):
    with open(config_path, "r") as f:
        read_config(f)


def stitch_videos():
    video_order = [timeline[i]["Video"] for i in range(len(timeline))]
    video_paths = [videos[vid_name][1] for vid_name in video_order]
    cmd = ["ffmpeg"]
    for video_path in video_paths:
        cmd.append("-i")
        cmd.append(video_path)
    # add the filter to concat videos
    cmd.append("-filter_complex")
    filter_text = "concat=n={}:v=1:a=1".format(len(video_paths))
    cmd.append(filter_text)
    # add the output name
    cmd.append("-y")
    cmd.append("./Data/output.mp4")
    # run the command
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            print(line, end="")


read_txt("./timeline.txt")
stitch_videos()
