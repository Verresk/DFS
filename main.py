import yaml
import subprocess
from pathlib import Path
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from imagededup.methods import PHash
import shutil


def load_config(cfg_path):
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f)


def extract_frames_ffmpeg(video_path, out_dir, fps):
    Path(out_dir).mkdir(exist_ok=True)
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vf', f'fps={fps}',
        f'{out_dir}/frame_%07d.jpg'
    ]
    subprocess.run(cmd)


def scene_split(video_path, threshold):
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=True)
    return scene_manager.get_scene_list()


def extract_boost_scenes(video_path, scenes, out_dir, fps_boost):
    Path(out_dir).mkdir(exist_ok=True)
    for i, (start, end) in enumerate(scenes):
        ss = start.get_timecode()
        to = end.get_timecode()
        cmd = [
            'ffmpeg',
            '-ss', ss,
            '-to', to,
            '-i', video_path,
            '-vf', f'fps={fps_boost}',
            f'{out_dir}/scene{i:03d}_%06d.jpg'
        ]
        subprocess.run(cmd)


def deduplicate_images(image_dir, output_dir, distance=10):
    ph = PHash()
    to_remove = ph.find_duplicates_to_remove(
        image_dir=image_dir,
        max_distance_threshold=distance
    )
    Path(output_dir).mkdir(exist_ok=True)
    imgs = set(Path(image_dir).glob("*.jpg"))
    to_keep = imgs - set(Path(image_dir)/img for img in to_remove)
    for img in to_keep:
        shutil.copy(img, Path(output_dir)/img.name)


def main():
    cfg = load_config("config.yaml")
    Path(cfg['output_dir']).mkdir(exist_ok=True)
    # 1) Грубая выборка
    extract_frames_ffmpeg(cfg['video_path'], f"{cfg['output_dir']}/frames_1fps", cfg['fps_main'])
    # 2) Определение сцен
    scenes = scene_split(cfg['video_path'], cfg['scene_threshold'])
    extract_boost_scenes(cfg['video_path'], scenes, f"{cfg['output_dir']}/frames_boost", cfg['fps_boost'])
    # 3) Дедупликация
    deduplicate_images(f"{cfg['output_dir']}/frames_1fps", f"{cfg['output_dir']}/dedup_1fps", cfg['dedup_distance'])
    deduplicate_images(f"{cfg['output_dir']}/frames_boost", f"{cfg['output_dir']}/dedup_boost", cfg['dedup_distance'])
    # 4) Финальная папка
    [shutil.copy(img, f"{cfg['output_dir']}/final/{img.name}") for folder in ['dedup_1fps', 'dedup_boost'] for img in Path(f"{cfg['output_dir']}/{folder}").glob("*.jpg")]
    print("Фреймы готовы к разметке!")

if __name__ == "__main__":
    main()
