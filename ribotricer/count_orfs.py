"""Utilities for translating ORF detection"""
# Part of ribotricer software
#
# Copyright (C) 2019 Wenzheng Li, Saket Choudhary and Andrew D Smith
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.


from collections import defaultdict
from .orf import ORF


def count_orfs(ribotricer_index,
               detected_orfs,
               features,
               prefix,
               report_all=False):
    """
    Parameters
    ----------
    ribotricer_index: str
                   Path to the index file generated by ribotricer prepare_orfs
    detected_orfs: str
                   Path to the detected orfs file generated by ribotricer detect_orfs
    features: set
              set of ORF types, such as {annotated}
    prefix: str
            prefix for output file
    report_all: bool
                if True, all coverages will be exported
    """
    orf_index = {}
    read_counts = defaultdict(dict)
    with open(ribotricer_index, 'r') as fin:
        # Skip header
        fin.readline()
        for line in fin:
            orf = ORF.from_string(line)
            if orf.category in features:
                orf_index[orf.oid] = orf
    with open(detected_orfs, 'r') as fin:
        # Skip header
        fin.readline()
        for line in fin:
            fields = line.strip().split('\t')
            oid, otype, status = fields[:3]
            gene_id, gene_name, gene_type = fields[9:12]
            chrom, strand, start_codon, profile = fields[12:]
            if otype in features:
                if status != 'nontranslating' or report_all:
                    intervals = orf_index[oid].intervals
                    coor = [x for iv in intervals for x in range(iv.start, iv.end + 1)]
                    if strand == '-':
                        coor = coor[::-1]
                    profile = list(map(int, profile.strip()[1:-1].split(', ')))
                    for pos, cov in zip(coor, profile):
                        if pos not in read_counts[gene_id, gene_name]:
                            read_counts[gene_id, gene_name][pos] = cov

    with open('{}_cnt.txt'.format(prefix), 'w') as fout:
        fout.write('gene_id\tcount\n')
        for gene_id, gene_name in sorted(read_counts):
            total = sum(read_counts[gene_id, gene_name].values())
            fout.write('{}\t{}\n'.format(gene_id, total))
