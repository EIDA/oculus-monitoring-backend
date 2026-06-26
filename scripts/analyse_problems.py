
for n in $node; do echo -n "$n "; grep -i $n zbx_problems_export.csv | grep -v -i certificat | grep -v -c "network code"; done | sort -k2 -n -r