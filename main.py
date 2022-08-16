import os
import subprocess


videos = []
timeline = []


def read_video_info(line):
    video_name = line.split(";")[0].strip()
    ref_frame = line.split(";")[1].strip()
    vid_path = line.split(";")[2].strip()
    videos.append({"Video": video_name, "Ref_Frame": ref_frame, "Path": vid_path})


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


def final_command():
    cmd = ["ffmpeg", "-framerate", "24", "-pattern_type", "glob", "-i",
           "24", "-pix_fmt", "yuv420p"]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    print(out)


read_txt("./timeline.txt")
print(videos)
print(timeline)
