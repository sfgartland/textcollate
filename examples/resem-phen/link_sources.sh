#!/bin/sh
# Symlink the source PDFs of this example into ./sources (paths as on the author's machine; edit as needed).
set -e
cd "$(dirname "$0")"; mkdir -p sources
Z="$HOME/zotfile"
ln -sfn "$Z/Uniemner/KU Leuven/PhD articulation/Husserl_1976_Die Krisis der europäischen Wissenschaften und die transzendentale Phänomenologie. Eine Einleitung i.pdf" sources/husserl-krisis-hua6-de.pdf
ln -sfn "$Z/Uniemner/KU Leuven/ReSem Phenomenology -- Husserl, the life world and technology/Husserl_1970_The crisis of european sciences and transcendental phenomenology. An introduction to phenomenologica.pdf" sources/husserl-crisis-carr-en.pdf
ln -sfn "$Z/Generell filosofi/Heidegger/Heidegger_2000_Die Frage nach der Technik.pdf" sources/heidegger-frage-nach-der-technik-ga7-de.pdf
ln -sfn "$Z/Generell filosofi/Heidegger/Heidegger_1977_The question concerning technology, and other essays.pdf" sources/heidegger-qct-lovitt-en.pdf
ls -l sources
