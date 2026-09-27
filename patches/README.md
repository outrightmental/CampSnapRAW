# patches/ — future home of firmware mods

Mods ship as binary diffs (xdelta3) against a specific stock firmware,
identified by SHA-256. Users apply them to firmware they obtained
themselves:

    xdelta3 -d -s stock-<sha256 prefix>.bin raw-v0.1.xdelta modded.bin

Nothing here yet — see ROADMAP.md Phase 3-4.
