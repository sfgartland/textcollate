#!/bin/sh
# Symlink the source files of this example into ./sources (they are not part of the repository: copyrighted scans).
# Edit the paths below if your files live elsewhere.
set -e
cd "$(dirname "$0")"
D="$HOME/Downloads/Heidegger_2000_GA16_Reden-und-andere-Zeugnisse"
ln -sfn "$D/gelassenheit-beyng/html" sources/beyng-html                                 # beyng.com pages GA16.517.html ...
ln -sf  "$HOME/Downloads/"Gesamtausgabe*Bd_16*.pdf sources/ga16-original-scan.pdf         # the untouched GA 16 scan (image only)
ln -sf  "$D/"Gelassenheit\ --\ Heidegger*.pdf sources/neske1960.pdf                       # Neske 1960 (text layer)
ln -sf  "$D/Memorial Address.pdf" sources/memorial-address.pdf                            # Discourse on Thinking pp. 43-57
ln -sf  "$D/Gelassenheit.pdf" sources/arendt-neske1959.pdf                                 # Arendt copy of Neske 1959 (Bard College), selected pages
ls -l sources
