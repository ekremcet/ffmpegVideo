import os
import shutil
import subprocess


videos = {}
timeline = []
video_order = []
video_fps = []
video_path = []


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


def get_frame_rate(video_path):
    # this is used to get framerate of video
    # framerate will be used to determine exact second to trim the video
    cmd = ["ffprobe", video_path, "-v", "0", "-select_streams", "v",
           "-print_format", "flat", "-show_entries", "stream=r_frame_rate"]
    out = subprocess.check_output(cmd)
    rate = out.decode("utf-8").split("=")[1].strip()[1:-1].split("/")
    if len(rate) == 1:
        return float(rate[0])
    elif len(rate) == 2:
        return float(rate[0]) / float(rate[1])
    return -1


def calculate_time_stamp(video, fps):
    video_start_frame = video["StartConfig"]["Frame"]
    video_end_frame = video["EndConfig"]["Frame"]

    start_time = float(video_start_frame)/fps
    end_time = float(video_end_frame)/fps

    return (start_time, end_time)


def trim_videos():
    print("Trimming videos with given frame numbers")
    # fill the global arrays (they will be used later as well)
    global video_order, video_paths, video_fps
    video_order = [timeline[i]["Video"] for i in range(len(timeline))]
    video_paths = [videos[vid_name][1] for vid_name in video_order]
    # get frame rate of each video to determine exact time stamp for trimming
    video_fps = [get_frame_rate(vid_path) for vid_path in video_paths]
    # calculate time stamps
    video_stamps = [calculate_time_stamp(video, video_fps[i]) for i, video in enumerate(timeline)]
    os.makedirs("./tmp", exist_ok=True)
    for i, video_path in enumerate(video_paths):
        # prepare videos individually
        start_time, end_time = video_stamps[i]
        cmd = ["ffmpeg", "-ss", str(start_time), "-to", str(end_time), "-i", video_path,
               "-vcodec", "copy", "-acodec", "copy", "-y", "./tmp/tmp_{}.mp4".format(i + 1)]
        # run the command
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()


def get_video_settings(video):
    video_speed = video["Speed"]
    if "Center" in video["StartConfig"]:
        video_start_center = video["StartConfig"]["Center"]
        video_start_res = video["StartConfig"]["Resolution"]
        video_end_center = video["EndConfig"]["Center"]
        video_end_res = video["EndConfig"]["Resolution"]
        return video_speed, video_start_center, video_start_res, video_end_center, video_end_res
    else:
        return video_speed


def scale_and_speed_videos():
    print("Changing speed and scale of the videos")
    video_settings = [get_video_settings(video) for i, video in enumerate(timeline)]
    for i, setting in enumerate(video_settings):
        # prepare videos individually
        speed = setting if len(setting) == 1 else setting[0]
        fps = video_fps[i]  # this is needed to change the frame rate, so frames are not dropped
        # change the speed first
        cmd = ["ffmpeg", "-i", "./tmp/tmp_{}.mp4".format(i + 1),
               "-filter_complex", "[0:v]setpts={}*PTS[v];[0:a]atempo={}[a]".format(1.0 / float(speed), speed),
               "-map", "[v]", "-map", "[a]", "-y", "./tmp/tmp_speed_{}.mp4".format(i + 1)]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if len(setting) == 1:
            # resolution will not change, so change the name
            os.rename("./tmp/tmp_speed_{}.mp4".format(i + 1), "./tmp/tmp_mod_{}.mp4".format(i + 1))
        else:
            # if resolution is given, change the resolution as well
            start_center, start_res = setting[1], setting[2]
            end_center, end_res = setting[3], setting[4]
            cmd = ["ffmpeg", "-i", "./tmp/tmp_speed_{}.mp4".format(i + 1),
                   "-vf", "scale={}".format(end_res), "-y", "./tmp/tmp_mod_{}.mp4".format(i + 1)]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = process.communicate()


def prepare_tmp_videos():
    # prepare tmp videos to stitch
    # trim, change scale, speed, etc. here
    print("Preparing tmp videos to stitch")
    trim_videos()
    scale_and_speed_videos()


def stitch_videos():
    print("Stitching final videos together")
    cmd = ["ffmpeg"]
    for i in range(len(timeline)):
        cmd.append("-i")
        cmd.append("./tmp/tmp_mod_{}.mp4".format(i + 1))
    # add the filter to concat videos
    cmd.append("-filter_complex")
    filter_text = "concat=n={}:v=1:a=1".format(len(timeline))
    cmd.append(filter_text)
    # add the output name
    cmd.append("-y")
    cmd.append("./Data/output.mp4")
    print(cmd)
    # run the command
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            print(line, end="")

    # delete the tmp folder
    shutil.rmtree("./tmp/", ignore_errors=False, onerror=None)


if __name__ == '__main__':
    read_txt("./timeline.txt")
    prepare_tmp_videos()
    stitch_videos()

