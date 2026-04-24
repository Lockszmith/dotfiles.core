#!/usr/bin/env bash
#
#  tar xvf db_dump.tar
#  cd db_dump
#

obj=$1
file=$(grep -E "COPY public.vmsapp_$obj" restore.sql | grep -Eow [0-9]+.dat)
cat ./$file | awk -F '\t' '{print $1 "\t" $3 "\t" $5}' | sort -k3 -V | grep -E '^[0-9]+'


