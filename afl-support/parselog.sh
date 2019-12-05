awk '{ split($8,A,"="); print $7, $8, "rate was", $9 / A[2] }' log
