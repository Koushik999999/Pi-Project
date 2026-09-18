# Pi Search — run locally

## Setup (one-time)
```
pip install gmpy2 flask
```
gmpy2 usually installs from a prebuilt wheel on Windows/Mac/Linux. If it fails to build,
install the GMP/MPFR/MPC dev libraries first (on Ubuntu/Debian: `sudo apt install libgmp-dev libmpfr-dev libmpc-dev`).

## Today: generate 300 million digits
```
python generate_pi.py --digits 300000000 --chunks 24 --out pi_300m.txt
```
- Expect **15–40 minutes** and **~4–6 GB RAM** on a typical modern desktop.
- It checkpoints each chunk to `pi_checkpoints/`. If it crashes or you Ctrl-C it,
  just re-run the exact same command — finished chunks are skipped automatically.
- At the end it self-checks the leading digits against the known value of pi and
  tells you PASSED/FAILED — trust the output only if it says PASSED.
- Delete the `pi_checkpoints/` folder once you have a working `pi_300m.txt`
  you're happy with (it's not needed after that, and it's roughly the same
  size as the final output).

## Run the search website
```
python search_server.py --file pi_300m.txt
```
Then open **http://localhost:5000**. Just start typing a digit string — it
searches live as you type (no button, no Enter needed) and reports the digit
position after the decimal point where it first occurs, with surrounding
context. Non-digit characters are blocked in the input, both client-side and
server-side. Uses `mmap`, so it doesn't need to load the whole file into RAM
to search it — this also means the exact same command works unmodified once
you have the 1-billion-digit file.

## Tomorrow: scaling to 1 billion digits

**Two ways to get there — pick based on how much time you want to spend:**

**Option A — reuse today's script (simplest, slower).**
```
python generate_pi.py --digits 1000000000 --chunks 64 --out pi_1b.txt
```
- Needs **~20–28 GB free RAM** and **2–5 hours** single-threaded.
- More chunks (64 instead of 24) means smaller/safer checkpoints, useful for a run this long.
- Run it overnight; check `pi_checkpoints/` in the morning — if it's still going,
  just let it keep running, it'll resume from the newest chunk if interrupted.
- `finalize()` divides the combined `Q`/`T` as an exact rational before converting
  to a float — this matters at these scales because `Q`/`T` individually run into
  the billions of bits, which overflows a plain float conversion even though their
  ratio is a normal-sized number. Already fixed and validated against known pi
  digits at 300M; no action needed, just don't "simplify" that line back to a
  direct float division.

**Option B — use y-cruncher instead (faster, same end result).**
y-cruncher (by Alexander Yee) is the actual program behind every pi world record —
multi-threaded, AVX-optimized, and dramatically faster than our pure-Python script.
1. Download it: https://www.numberworld.org/y-cruncher/ (Windows and Linux builds)
2. Run: `y-cruncher.exe pi -digits:1000000000 -algorithm:chudnovsky -output:pi_1b.txt`
   (exact flags vary slightly by version — the program has a config menu if the
   CLI syntax differs)
3. On a modern multi-core desktop this typically finishes in **10–20 minutes**,
   not hours, because it uses all your CPU cores and vectorized instructions.
4. Once you have `pi_1b.txt`, point the *same* `search_server.py` at it — nothing
   else changes:
   ```
   python search_server.py --file pi_1b.txt
   ```

**Either way, the search website code doesn't change.** That's the point of the
mmap-based design: whether the file is 300 MB or 1 GB, search stays fast (well
under a second) because the OS pages in only the parts of the file actually
touched during the scan, and `bytes.find` is implemented in optimized C.

## Beyond 1 billion (for context, not for tomorrow)
Going to 10B or 100B digits is a different kind of problem — it needs 100s of GB
to TB of RAM (that's genuinely what the real world-record y-cruncher runs used,
per their published benchmark logs), so it means renting a large cloud VM for
hours-to-days, not running a script on a laptop. Worth revisiting only if 1B
turns out to not be "enough."
