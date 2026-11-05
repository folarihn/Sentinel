"""Assemble a source-labeled under-90-second walkthrough from genuine UI captures.

The 25-second host segment is a continuous browser-frame recording. Other
segments are explicitly labeled recorded evidence stills. No telemetry is made
up, no model output is reconstructed, and no audio/voiceover is synthesized.
Requires an installed FFmpeg; no media is uploaded.
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path


SCENES = [
    (
        8,
        "overview-desktop.jpg",
        "RECORDED REAL MODEL EVIDENCE",
        "SENTINEL OS: autonomy with accountability.",
    ),
    (
        10,
        "model-replay.jpg",
        "RECORDED MODEL TASK",
        "Hermes repaired greeting.py inside a bounded mission.",
    ),
    (
        12,
        "model-blocks.jpg",
        "GENUINE MODEL ATTEMPTS BLOCKED",
        "Secret access, destructive shell and out-of-scope writing were blocked.",
    ),
    (
        10,
        "actual-human-once-detail.jpg",
        "ACTUAL OWNER DECISION VIA NATIVE CALLBACK",
        "The owner chose once. Real writes followed; human rejection is not claimed.",
    ),
    (
        25,
        None,
        "CONTINUOUS LIVE HOST-TOOL RECORDING",
        "Actual Hermes write, checkpoint and restoration arrive in Watch. No model request here.",
    ),
    (
        10,
        "recovery-desktop.jpg",
        "VERIFIED FILE RESTORATION",
        "Original bytes restored after real operations. External side effects cannot be undone.",
    ),
    (
        8,
        "missions-desktop.jpg",
        "BOUNDED AUTHORITY",
        "Permissions persist in the backend. These verified missions are completed.",
    ),
    (
        6,
        "mesh-desktop.jpg",
        "TRUTHFUL SESSION ATTRIBUTION",
        "Separate model and host sessions. Review the pinned release and disclosures before installing.",
    ),
]


def run(argv, cwd=None):
    subprocess.run(
        argv, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screenshots", type=Path, default=Path("docs/screenshots/release")
    )
    parser.add_argument("--recording", type=Path, default=Path(".tools/demo-recording"))
    parser.add_argument(
        "--output", type=Path, default=Path("dist/sentinel-demo-89s.mp4")
    )
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit(
            "Install FFmpeg from its official distribution before rendering"
        )
    root = args.recording.resolve()
    segments = root / "segments"
    segments.mkdir(exist_ok=True)
    frames = json.loads((root / "frames.json").read_text(encoding="utf-8"))
    if frames["elapsed_ms"] < 25000:
        raise ValueError("The genuine continuous host recording must cover 25 seconds")
    manifest = []
    for index, frame in enumerate(frames["frames"]):
        next_time = (
            frames["frames"][index + 1]["time_ms"]
            if index + 1 < len(frames["frames"])
            else frames["elapsed_ms"]
        )
        manifest.extend(
            [
                f"file 'frames/{frame['file']}'",
                f"duration {(next_time - frame['time_ms']) / 1000:.6f}",
            ]
        )
    manifest.append(f"file 'frames/{frames['frames'][-1]['file']}'")
    (root / "live-frames.txt").write_text("\n".join(manifest), encoding="utf-8")
    timeline = []
    elapsed = 0
    for index, (duration, screenshot, title, narration) in enumerate(SCENES):
        output = segments / f"scene-{index}.mp4"
        source = (
            ["-loop", "1", "-i", str((args.screenshots / screenshot).resolve())]
            if screenshot
            else ["-f", "concat", "-safe", "0", "-i", str(root / "live-frames.txt")]
        )
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                *source,
                "-t",
                str(duration),
                "-vf",
                "scale=1440:1000:force_original_aspect_ratio=decrease,pad=1440:1000:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-r",
                "24",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                str(output),
            ]
        )
        timeline.append(
            {
                "start": elapsed,
                "end": elapsed + duration,
                "source": "genuine screenshot still"
                if screenshot
                else "continuous genuine browser recording",
                "title": title,
                "narration": narration,
            }
        )
        elapsed += duration
    (root / "segments.txt").write_text(
        "\n".join(f"file 'segments/scene-{i}.mp4'" for i in range(len(SCENES))),
        encoding="utf-8",
    )

    def ass_time(seconds):
        return f"0:{seconds // 60:02d}:{seconds % 60:02d}.00"

    ass = "[Script Info]\nScriptType: v4.00+\nPlayResX: 1440\nPlayResY: 1000\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Segoe UI,25,&H00E5E9E8,&H00E5E9E8,&H00110D09,&H00110D09,0,0,0,0,100,100,0,0,3,12,0,2,30,30,25,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    for scene in timeline:
        ass += f"Dialogue: 0,{ass_time(scene['start'])},{ass_time(scene['end'])},Default,,0,0,0,,{scene['title']}\\N{scene['narration']}\n"
    (root / "captions.ass").write_text(ass, encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            "segments.txt",
            "-vf",
            "ass=captions.ass",
            "-t",
            str(elapsed),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(args.output.resolve()),
        ],
        cwd=root,
    )
    report = {
        "duration_seconds": elapsed,
        "voiceover": "none; captioned evidence walkthrough with separate narration script",
        "media": "genuine browser captures only",
        "continuous_live_host_recording_seconds": 25,
        "timeline": timeline,
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"rendered": True, "duration_seconds": elapsed, "output": str(args.output)}
        )
    )


if __name__ == "__main__":
    main()
