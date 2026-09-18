"""
Generate N digits of pi, chunked and checkpointed so a crash/interrupt doesn't
cost you the whole run — just re-run the same command and it resumes.

Usage:
    python generate_pi.py --digits 300000000 --chunks 24 --out pi_300m.txt

For the 1-billion run tomorrow, just change --digits (and maybe --chunks, more
chunks = smaller checkpoints = safer resume granularity):
    python generate_pi.py --digits 1000000000 --chunks 64 --out pi_1b.txt
"""
import argparse
import os
import pickle
import time
import sys

from pi_gen import bs, tree_combine, finalize


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, required=True)
    ap.add_argument("--chunks", type=int, default=24)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--checkpoint-dir", type=str, default="pi_checkpoints")
    args = ap.parse_args()

    os.makedirs(args.checkpoint_dir, exist_ok=True)

    terms = args.digits // 14 + 2
    chunk_size = terms // args.chunks + 1
    bounds = []
    a = 0
    while a < terms:
        b = min(a + chunk_size, terms)
        bounds.append((a, b))
        a = b

    log(f"target digits={args.digits:,}  terms={terms:,}  chunks={len(bounds)}")

    partials = [None] * len(bounds)
    for i, (a, b) in enumerate(bounds):
        ckpt_path = os.path.join(args.checkpoint_dir, f"chunk_{i:04d}.pkl")
        if os.path.exists(ckpt_path):
            with open(ckpt_path, "rb") as f:
                partials[i] = pickle.load(f)
            log(f"chunk {i+1}/{len(bounds)} [{a:,}:{b:,}) — loaded from checkpoint")
            continue
        t0 = time.time()
        result = bs(a, b)
        with open(ckpt_path, "wb") as f:
            pickle.dump(result, f)
        partials[i] = result
        log(f"chunk {i+1}/{len(bounds)} [{a:,}:{b:,}) — computed in {time.time()-t0:.1f}s")

    log("merging chunks (balanced tree)...")
    t0 = time.time()
    _, Q, T = tree_combine(partials)
    log(f"merge done in {time.time()-t0:.1f}s")

    log("finalizing (sqrt + division + string conversion — this step is the slowest single step)...")
    t0 = time.time()
    digit_string = finalize(Q, T, args.digits)
    log(f"finalize done in {time.time()-t0:.1f}s")

    with open(args.out, "w") as f:
        f.write(digit_string)
    log(f"wrote {len(digit_string):,} characters to {args.out}")

    # sanity check against known leading digits of pi
    known_prefix = "314159265358979323846264338327950288419716939937510"
    if digit_string.replace(".", "")[:len(known_prefix)] == known_prefix:
        log("sanity check PASSED (leading digits match known pi)")
    else:
        log("sanity check FAILED — leading digits do not match known pi. Do not trust this output.")


if __name__ == "__main__":
    main()
