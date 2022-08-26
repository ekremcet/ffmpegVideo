import os
import signal
import shutil
import subprocess


videos = {}
timeline = []
video_order = []
audio_paths = []
video_fps = []
video_durations = []
video_paths = []


def read_video_info(line):
    video_name = line.split(";")[1].strip()
    ref_frame = line.split(";")[2].strip()
    audio_path = line.split(";")[3].strip()
    vid_path = line.split(";")[4].strip()
    videos[video_name] = (ref_frame, audio_path, vid_path)


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

    timeline.append({"Video": video_name, "Speed": speed,
                     "StartConfig": start_config, "EndConfig": end_config})


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


def get_video_frame_info(video_path):
    # this is used to get framerate of video
    # framerate will be used to determine exact second to trim the video
    cmd = ["ffprobe", video_path, "-v", "0", "-select_streams", "v",
           "-print_format", "flat", "-show_entries", "stream=r_frame_rate, duration"]
    out = subprocess.check_output(cmd)
    rate_line, duration_line = out.decode("utf-8").split("\n")[:-1]
    rate = rate_line.split("=")[1].strip()[1:-1].split("/")
    duration = duration_line.split("=")[1].strip()[1:-1]
    if len(rate) == 1:
        return float(rate[0]), float(duration)
    elif len(rate) == 2:
        return float(rate[0]) / float(rate[1]), float(duration)
    return -1, -1


def calculate_time_stamp(video, fps, duration):
    video_start_frame = video["StartConfig"]["Frame"]
    video_end_frame = video["EndConfig"]["Frame"]

    start_time = float(video_start_frame)/fps
    end_time = float(video_end_frame)/fps

    if start_time > duration:
        # ignore the clip
        return -1, -1
    elif end_time > duration:
        return start_time, duration
    else:
        return start_time, end_time


def trim_videos():
    print("Trimming videos with given frame numbers")
    # fill the global arrays (they will be used later as well)
    global timeline, video_order, audio_paths, video_paths, video_fps, video_durations
    video_order = [timeline[i]["Video"] for i in range(len(timeline))]
    audio_paths = [videos[vid_name][1] for vid_name in video_order]
    video_paths = [videos[vid_name][2] for vid_name in video_order]
    # get frame rate and duration of each video to determine exact time stamp for trimming
    for vid_path in video_paths:
        fps, duration = get_video_frame_info(vid_path)
        video_fps.append(fps)
        video_durations.append(duration)
    # calculate time stamps
    video_stamps = [calculate_time_stamp(video, video_fps[i], video_durations[i])
                    for i, video in enumerate(timeline)]
    os.makedirs("./tmp", exist_ok=True)
    vid_ind = 0
    for i, video_path in enumerate(video_paths):
        # prepare videos individually
        start_time, end_time = video_stamps[i]
        if start_time == -1:
            # skip this clip and remove information from lists
            del timeline[i]
            del audio_paths[i]
            del video_order[i]
            del video_fps[i]
            del video_durations[i]
            continue
        cmd = ["ffmpeg", "-ss", str(start_time), "-to", str(end_time), "-i", video_path,
               "-c:v", "copy", "-c:a", "copy", "-y", "./tmp/tmp_{}.mp4".format(vid_ind + 1)]
        # run the command
        vid_ind += 1
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()


def get_video_settings(i, video):
    video_speed = video["Speed"]
    mod_aud = False if len(audio_paths[i]) == 1 else True  # if there is no audio path don't modify audio
    if "Center" in video["StartConfig"]:
        video_start_center = video["StartConfig"]["Center"]
        video_start_res = video["StartConfig"]["Resolution"]
        video_start_frame = video["StartConfig"]["Frame"]
        video_end_center = video["EndConfig"]["Center"]
        video_end_res = video["EndConfig"]["Resolution"]
        video_end_frame = video["EndConfig"]["Frame"]
        return video_speed, mod_aud, video_start_center, video_start_res, video_end_center, video_end_res, \
               video_start_frame, video_end_frame
    else:
        return video_speed, mod_aud


def add_dummy_silent_track(i):
    cmd = ["ffmpeg", "-i", "./tmp/tmp_{}.mp4".format(i + 1), "-f",
           "lavfi", "-i", "anullsrc", "-shortest", "-c:v", "copy",
           "-y", "./tmp/tmp_dum_{}.mp4".format(i + 1)]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()


def add_audio_track(i):
    audio_path = audio_paths[i]
    cmd = ["ffmpeg", "-i", "./tmp/tmp_{}.mp4".format(i + 1),
           "-i", audio_path, "-map", "0:v", "-map", "1:a", "-codec", "copy",
           "-shortest", "-y", "./tmp/tmp_dum_{}.mp4".format(i + 1)]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()


def change_speed(i, input_name, speed):
    cmd = ["ffmpeg", "-i", input_name,
            "-filter_complex", "[0:v]setpts={}*PTS[v];[0:a]atempo={}[a]".format(1.0 / float(speed), speed),
            "-map", "[v]", "-map", "[a]",
            "-y", "./tmp/tmp_speed_{}.mp4".format(i + 1)]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()


def zoompan_cmd(zoom_f, speed, fps, end_res, start_frame, end_frame):
    # find the zoom scale increase per frame based on the clip length
    # S = (zoom_f - 1) / num_frames
    # Don't forget the speed change
    num_frames = (int(end_frame) - int(start_frame)) / float(speed)
    zoom_per_frame = float((zoom_f - 1) / num_frames)
    cmd = "zoompan=z="
    # first zooming to the location
    cmd += "'min(max(zoom,pzoom)+{},{})':d=0".format(zoom_per_frame, zoom_f)
    # change the x scale
    cmd += ":x='iw/{}-(iw/zoom/{})'".format(zoom_f, zoom_f)
    # change the y scale
    cmd += ":y='ih/{}-(ih/zoom/{})'".format(zoom_f, zoom_f)
    # define fps and final scale
    cmd += ":fps={}':s={}'".format(fps, end_res)

    return cmd


def zoom(i, input_name, setting):
    speed = setting[0]
    start_center, start_res = setting[2], setting[3]
    end_center, end_res = setting[4], setting[5]
    start_center_x = start_center.split("x")[0].strip()
    start_width = start_res.split("x")[0].strip()
    start_frame, end_frame = setting[6], setting[7]

    # find the duration of zoom/pan
    fps = video_fps[i]
    # find the zoom factor
    zoom_f = int(start_width) / int(start_center_x)

    zoompan = zoompan_cmd(zoom_f, speed, fps, end_res, start_frame, end_frame)

    cmd = ["ffmpeg", "-i", input_name,
           "-vf", "{}".format(zoompan),
           "-y", "./tmp/tmp_mod_{}.mp4".format(i + 1)]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()


def check_required_changes(setting):
    speed = setting[0]
    mod_aud = setting[1]

    changeAudio = mod_aud
    changeSpeed = (speed != "1")
    doZoom = len(setting) != 2

    return changeAudio, changeSpeed, doZoom


def change_speed_and_zoom(i, inp_name, setting, flags):
    _, speedFlag, zoomFlag = flags
    speed = setting[0]
    if speedFlag:
        # audio, speed
        change_speed(i, inp_name, speed)
        inp_name = "./tmp/tmp_speed_{}.mp4".format(i + 1)
        if zoomFlag:
            # audio, speed, zoom
            zoom(i, inp_name, setting)
        else:
            # audio, speed, no zoom
            os.rename(inp_name, "./tmp/tmp_mod_{}.mp4".format(i + 1))
    else:
        if zoomFlag:
            # audio, no speed, zoom
            zoom(i, inp_name, setting)
        else:
            # audio, no speed, no zoom
            os.rename(inp_name, "./tmp/tmp_mod_{}.mp4".format(i + 1))


def make_required_changes(i, setting, flags):
    audioFlag, speedFlag, zoomFlag = flags
    if audioFlag:
        # audio
        # add_dummy_silent_track(i) -> ignore it, no more use case
        add_audio_track(i)
        inp_name = "./tmp/tmp_dum_{}.mp4".format(i + 1)
        change_speed_and_zoom(i, inp_name, setting, flags)
    else:
        # no audio
        inp_name = "./tmp/tmp_{}.mp4".format(i + 1)
        change_speed_and_zoom(i, inp_name, setting, flags)


def scale_and_speed_videos():
    print("Changing speed and scale of the videos")
    video_settings = [get_video_settings(i, video) for i, video in enumerate(timeline)]
    # prepare videos individually
    for i, setting in enumerate(video_settings):
        # check required changes first
        flags = check_required_changes(setting)
        make_required_changes(i, setting, flags)


def prepare_tmp_videos():
    # prepare tmp videos to stitch
    # trim, change scale, speed, etc. here
    print("Preparing tmp videos to stitch")
    trim_videos()
    scale_and_speed_videos()


def delete_tmp_folder():
    # delete the tmp folder
    if os.path.exists("./tmp/"):
        pass
        shutil.rmtree("./tmp/", ignore_errors=False, onerror=None)


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
    # run the command
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            print(line, end="")

    delete_tmp_folder()


def sigterm_handler(_signo, _stack_frame):
    # catch the interrupted subprocess here
    delete_tmp_folder()


if __name__ == '__main__':
    try:
        signal.signal(signal.SIGTERM, sigterm_handler)
        read_txt("./timeline.txt")
        prepare_tmp_videos()
        stitch_videos()
    except KeyboardInterrupt:
        print("Exiting...")
        delete_tmp_folder()
    except Exception:
        print("Error occurred, stopping the program..")
        delete_tmp_folder()
