"""Time and memory of whole-image segmentation on one image, per device and thread count.

Usage: python tools/benchmark_segmentation.py IMAGE [--weights PATH] [--threads 16 4] [--runs 3]
"""

import argparse
import resource
import time

import numpy as np
from PIL import Image

from rhizotrace.segmentation import load_segmenter


def bench(img, device, threads, weights, runs):
    import torch
    if device == "cpu":
        torch.set_num_threads(threads)
    s = load_segmenter(weights, device=device)
    s.check_memory = False
    s.segment(img)                                  # warm-up (cuda init, allocator)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        s.segment(img)
        if device == "cuda":
            torch.cuda.synchronize()
        times.append(time.perf_counter() - t)
    if device == "cuda":
        mem = torch.cuda.max_memory_allocated() / 1e9
        label = torch.cuda.get_device_name(0)
    else:
        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
        label = f"CPU, {threads} threads"
    return label, float(np.median(times)), mem


def main():
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("--weights")
    p.add_argument("--threads", type=int, nargs="+", default=[16, 4])
    p.add_argument("--runs", type=int, default=3)
    args = p.parse_args()
    import torch

    img = np.asarray(Image.open(args.image).convert("RGB"))
    mp = img.shape[0] * img.shape[1] / 1e6
    print(f"image {img.shape[1]} x {img.shape[0]} px ({mp:.1f} MP)\n")
    print("| device | seconds per image | peak memory (GB) |\n|---|---|---|")
    if torch.cuda.is_available():
        label, t, mem = bench(img, "cuda", None, args.weights, args.runs)
        print(f"| GPU ({label}) | {t:.1f} | {mem:.1f} GPU |")
    for threads in args.threads:
        label, t, mem = bench(img, "cpu", threads, args.weights, args.runs)
        print(f"| {label} | {t:.1f} | {mem:.1f} RAM (process peak) |")


if __name__ == "__main__":
    main()
