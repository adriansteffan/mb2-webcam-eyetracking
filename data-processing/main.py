import cv2
import json

import os
from os import listdir
from os.path import isfile, join
import subprocess

import statistics

# information is not present in the data output, fix this at some point in time
STIMULUS_ASPECT_RATIO = 4.0/3.0

data_directory = "../prod_mb2-webcam-eyetracking/data"
media_directory = "../media/video"
output_directory = "./output"

if not os.path.exists(output_directory):
    os.makedirs(output_directory)


def translate_coordinates(video_aspect_ratio, win_height, win_width, vid_height, vid_width, winX, winY):
    if win_width/win_height > video_aspect_ratio:  # full height video
        vid_on_screen_width = win_height*video_aspect_ratio

        if winX < (win_width - vid_on_screen_width)/2 or winX > ((win_width - vid_on_screen_width)/2 + vid_on_screen_width):
            return None, None
        # scale x
        vidX = ((winX - (win_width - vid_on_screen_width)/2) / vid_on_screen_width) * vid_width
        # scale y
        vidY = (winY/win_height)*vid_height
        return int(vidX), int(vidY)
    else:  # full width video
        # TODO cutoff for other aspect ratios
        vidX = (winX / win_width) * vid_width
        return None, None


def tag_video(path, json_data, media_name, participant_name):

    """ combine media and webcam video """

    pre1_path = output_directory+"/"+participant_name+"/pre1_" + media_name + ".mp4"
    pre2_path = output_directory+"/"+participant_name+"/pre2_" + media_name + ".mp4"
    final_path = output_directory +"/"+ participant_name +"/tagged_"+ media_name + ".mp4"

    if True:
        p1 = subprocess.Popen(['ffmpeg',
                         '-y',
                         '-i',
                         media_directory+"/"+media_name+".mp4",
                         "-vf",
                         "movie="+data_directory+"/"+participant_name+"_"+media_name+".webm, scale=350: -1 [inner]; [in][inner] overlay =10: 10 [out]",
                         pre1_path
                         ])

        p1.wait()
        p2 = subprocess.Popen(['ffmpeg',
                         '-y',
                         '-i',
                         pre1_path,
                         '-vf',
                         "drawtext=fontfile=Arial.ttf: text='%{frame_num} / %{pts}': start_number=1: x=(w-tw)/2: y=h-lh: fontcolor=black: fontsize=(h/20): box=1: boxcolor=white: boxborderw=5",
                         "-c:a",
                         "copy",
                         "-c:v",
                         "libx264",
                         "-crf",
                         "23",
                         pre2_path,
                         ])
        p2.wait()

    """ tag the video with eye tracking data """

    win_width = json_data['windowWidth']
    win_height = json_data['windowHeight']
    gaze_points = json_data['webgazer_data']
    gaze_point_index = 1

    video = cv2.VideoCapture(pre2_path)
    fps = video.get(cv2.CAP_PROP_FPS)
    vid_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    vid_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    size = (vid_height, vid_width)

    video_writer = cv2.VideoWriter(final_path, cv2.VideoWriter_fourcc('m','p','4','v'), fps, (vid_width, vid_height), True)
    success, frame = video.read()
    index = 1

    while success:

        if gaze_point_index < len(gaze_points) - 1 and gaze_points[gaze_point_index + 1]['t'] <= (index/fps)*1000:
            gaze_point_index += 1

        curr_gaze_point = gaze_points[gaze_point_index]
        x, y = translate_coordinates(STIMULUS_ASPECT_RATIO,
                                     win_height,
                                     win_width,
                                     vid_height,
                                     vid_width,
                                     curr_gaze_point['x'],
                                     curr_gaze_point['y']
                                     )

        #print("gaze x: " + str(curr_gaze_point['x']) + ",gaze y: " + str(curr_gaze_point['y']))
        #print("x: " + str(x) + ",y: " + str(y))

        if x is not None and y is not None:
            cv2.circle(frame, (x, y), radius=10, color=(255, 0, 0), thickness=-1)

        cv2.imshow(media_name, frame)
        cv2.waitKey(int(1000 / int(fps)))
        video_writer.write(frame)
        success, frame = video.read()
        index += 1
    video.release()


files = [f for f in listdir(data_directory) if isfile(join(data_directory, f))]
participants = set()
trials = set()

for filename in files:
    if filename.startswith(".") or filename.endswith(".json"):
        continue
    try:
        filename_split = filename.split("_")
        participant = "_".join(filename_split[:2])
        trial = ".".join("_".join(filename_split[2:]).split(".")[:-1])
    except:
        continue
    participants.add(participant)
    trials.add(trial)

videos = [t for t in trials if "_" in t]
print(videos)
print(participants)


for p in participants:

    if not os.path.exists(output_directory+"/"+p):
        os.makedirs(output_directory+"/"+p)

    json_path = data_directory + "/" + p + "_data.json"
    with open(json_path) as f:
        data = json.load(f)
    data = [x for x in data if 'task' in x and x['task'] == 'video']

    mean_sum = 0
    sd_sum = 0
    for v in videos:
        # only get the data of the correct stimulus
        filtered = [x for x in data if x['stimulus'][0].split("/")[-1].split(".")[0] == v]
        if len(filtered) < 1:
            continue

        video_path = data_directory + "/" + p + "_" + v + ".webm"
        output_path = "."
        #tag_video(video_path, filtered[0], v, p)

        # calulate mean and sd for sampling rate
        datapoints = filtered[0]['webgazer_data']
        sampling_diffs = [datapoints[i+1]['t']-datapoints[i]['t'] for i in range(1, len(datapoints)-1)]
        sampling_rates = [1000/diff for diff in sampling_diffs]
        mean_sum += statistics.mean(sampling_rates)
        sd_sum += statistics.stdev(sampling_rates)

    #print(p)
    #print("mean sampling rate: " + str(mean_sum/6))
    #print("sd sampling rate: " + str(sd_sum /6))


