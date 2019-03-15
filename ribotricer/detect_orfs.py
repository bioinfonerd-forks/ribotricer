"""Utilities for translating ORF detection"""

import warnings

from collections import Counter
from collections import defaultdict

import datetime
import numpy as np
from tqdm import *
import pandas as pd

from .bam import split_bam
from bx.intervals.intersection import IntervalTree
from .const import CUTOFF
from .const import MINIMUM_VALID_CODONS
from .fasta import FastaReader
from .gtf import GTFReader
from .infer_protocol import infer_protocol
from .metagene import metagene_coverage
from .metagene import align_metagenes
from .orf import ORF
from .plotting import plot_read_lengths
from .plotting import plot_metagene
from .prepare_orfs import prepare_orfs
from .statistics import coherence


def merge_read_lengths(alignments, psite_offsets):
    """
    Parameters
    ----------
    alignments: dict(dict(Counter))
                bam split by length, strand
    psite_offsets: dict
                   key is the length, value is the offset
    Returns
    -------
    merged_alignments: dict(dict)
                       alignments by merging all lengths
    """
    # print('merging different lengths...')
    merged_alignments = defaultdict(Counter)

    for length, offset in list(psite_offsets.items()):
        for strand in alignments[length]:
            for chrom, pos in alignments[length][strand]:
                count = alignments[length][strand][(chrom, pos)]
                if strand == '+':
                    pos_shifted = pos + offset
                else:
                    pos_shifted = pos - offset
                merged_alignments[strand][(chrom, pos_shifted)] += count
    return merged_alignments


def parse_ribotricer_index(ribotricer_index):
    """
    Parameters
    ----------
    ribotricer_index: str
                   Path to the index file generated by ribotricer prepare_orfs

    Returns
    -------
    annotated: List[ORF]
               ORFs of CDS annotated
    novel: List[ORF]
           list of non-annotated ORFs
    refseq: defaultdict(IntervalTree)
            chrom: (start, end, strand)
    """

    annotated = []
    refseq = defaultdict(IntervalTree)

    # print('parsing candidate ORFs...')
    total_lines = 0
    with open(ribotricer_index, 'r') as anno:
        for line in anno:
            if 'annotated' in anno:
                total_lines += 1
            else:
                break
    with open(ribotricer_index, 'r') as anno:
        with tqdm(total=total_lines) as pbar:
            header = True
            for line in anno:
                pbar.update()
                if header:
                    header = False
                    continue
                orf = ORF.from_string(line)
                if orf is None:
                    continue
                if orf.category == 'annotated':
                    refseq[orf.chrom].insert(orf.intervals[0].start,
                                             orf.intervals[-1].end, orf.strand)
                    annotated.append(orf)
                else:
                    break
    return (annotated, refseq)


def orf_coverage(orf, alignments, offset_5p=0, offset_3p=0):
    """
    Parameters
    ----------
    orf: ORF
         instance of ORF
    alignments: dict(Counter)
                alignments summarized from bam by merging lengths
    offset_5p: int
               the number of nts to include from 5'prime
    offset_3p: int
               the number of nts to include from 3'prime

    Returns
    -------
    coverage: array
              coverage for ORF
    """
    coverage = []
    chrom = orf.chrom
    strand = orf.strand
    if strand == '-':
        offset_5p, offset_3p = offset_3p, offset_5p
    first, last = orf.intervals[0], orf.intervals[-1]
    for pos in range(first.start - offset_5p, first.start):
        if orf.category == 'annotated':
            try:
                coverage.append(alignments[strand][(chrom, pos)])
            except KeyError:
                coverage.append(0)
        else:
            if strand in alignments and (chrom, pos) in alignments[strand]:
                coverage.append(alignments[strand][(chrom, pos)])
            else:
                coverage.append(0)

    for iv in orf.intervals:
        for pos in range(iv.start, iv.end + 1):
            if orf.category == 'annotated':
                try:
                    coverage.append(alignments[strand][(chrom, pos)])
                except KeyError:
                    coverage.append(0)
            else:
                if strand in alignments and (chrom, pos) in alignments[strand]:
                    coverage.append(alignments[strand][(chrom, pos)])
                else:
                    coverage.append(0)

    for pos in range(last.end + 1, last.end + offset_3p + 1):
        if orf.category == 'annotated':
            try:
                coverage.append(alignments[strand][(chrom, pos)])
            except KeyError:
                coverage.append(0)
        else:
            if strand in alignments and (chrom, pos) in alignments[strand]:
                coverage.append(alignments[strand][(chrom, pos)])
            else:
                coverage.append(0)

    if strand == '-':
        coverage.reverse()
    return coverage


def export_orf_coverages(ribotricer_index,
                         merged_alignments,
                         prefix,
                         report_all=False):
    """
    Parameters
    ----------
    ribotricer_index: str
                   Path to the index file generated by ribotricer prepare_orfs
    merged_alignments: dict(dict)
                       alignments by merging all lengths
    prefix: str
            prefix for output file
    report_all: bool
                if True, all coverages will be exported
    """
    # print('exporting coverages for all ORFs...')
    columns = [
        'ORF_ID', 'ORF_type', 'status', 'phase_score', 'read_count', 'length',
        'valid_codons', 'transcript_id', 'transcript_type', 'gene_id',
        'gene_name', 'gene_type', 'chrom', 'strand', 'start_codon', 'profile\n'
    ]
    to_write = '\t'.join(columns)
    formatter = '{}\t' * (len(columns) - 1) + '{}\n'
    with open(ribotricer_index, 'r') as anno:
        total_lines = len(['' for line in anno])

    with open(ribotricer_index, 'r') as anno, open(
            '{}_translating_ORFs.tsv'.format(prefix), 'w') as output:
        with tqdm(total=total_lines) as pbar:
            header = True
            for line in anno:
                pbar.update()
                if header:
                    header = False
                    output.write(to_write)
                    continue
                orf = ORF.from_string(line)
                cov = orf_coverage(orf, merged_alignments)
                count = sum(cov)
                length = len(cov)
                coh, valid = coherence(cov)
                status = 'translating' if (
                    coh >= CUTOFF
                    and valid >= MINIMUM_VALID_CODONS) else 'nontranslating'
                # skip outputing nontranslating ones
                if not report_all and status == 'nontranslating':
                    continue
                to_write = formatter.format(
                    orf.oid, orf.category, status, coh, count, length, valid,
                    orf.tid, orf.ttype, orf.gid, orf.gname, orf.gtype,
                    orf.chrom, orf.strand, orf.start_codon, cov)
                output.write(to_write)

    # now = datetime.datetime.now()
    # print('{} ... {}'.format(
    #     now.strftime('%b %d %H:%M:%S'), 'started saving results into disk'))
    # with open('{}_translating_ORFs.tsv'.format(prefix), 'w') as output:
    #     output.write(to_write)


def export_wig(merged_alignments, prefix):
    """
    Parameters
    ----------
    merged_alignments: dict(dict)
                       alignments by merging all lengths
    prefix: str
            prefix of output wig files
    """
    # print('exporting merged alignments to wig file...')
    for strand in merged_alignments:
        to_write = ''
        cur_chrom = ''
        for chrom, pos in sorted(merged_alignments[strand]):
            if chrom != cur_chrom:
                cur_chrom = chrom
                to_write += 'variableStep chrom={}\n'.format(chrom)
            to_write += '{}\t{}\n'.format(
                pos, merged_alignments[strand][(chrom, pos)])
        if strand == '+':
            fname = '{}_pos.wig'.format(prefix)
        else:
            fname = '{}_neg.wig'.format(prefix)
        with open(fname, 'w') as output:
            output.write(to_write)


def detect_orfs(bam, ribotricer_index, prefix, protocol, read_lengths,
                psite_offsets, report_all):
    """
    Parameters
    ----------
    bam: str
         Path to the bam file
    ribotricer_index: str
                   Path to the index file generated by ribotricer prepare_orfs
    prefix: str
            prefix for all output files
    protocol: str
              {'forward', 'no', 'reverse'}
              If None, the protocolness will be automatically inferred
    read_lengths: list[int]
                  read lengths to use
                  If None, it will be automatically determined by assessing
                  the periodicity of metagene profile of this read length
    psite_offsets: dict
                   Psite offsets for each read lengths
                   If None, the profiles from different read lengths will be
                   automatically aligned using cross-correlation
    report_all: bool
                Whether to output all ORFs' scores regardless of translation
                status
    """
    now = datetime.datetime.now()
    print(now.strftime('%b %d %H:%M:%S ..... started ribotricer detect-orfs'))

    ### parse the index file
    now = datetime.datetime.now()
    print(
        now.strftime('%b %d %H:%M:%S ... started parsing ribotricer index file'))
    annotated, refseq = parse_ribotricer_index(ribotricer_index)

    ### infer experimental protocol if not provided
    if protocol is None:
        now = datetime.datetime.now()
        print('{} ... {}'.format(
            now.strftime('%b %d %H:%M:%S'),
            'started inferring experimental design'))
        protocol = infer_protocol(bam, refseq, prefix)
    del refseq

    ### split bam file into strand and read length
    now = datetime.datetime.now()
    print(now.strftime('%b %d %H:%M:%S ... started reading bam file'))
    alignments, read_length_counts = split_bam(bam, protocol, prefix,
                                               read_lengths)

    ### plot read length distribution
    now = datetime.datetime.now()
    print('{} ... {}'.format(
        now.strftime('%b %d %H:%M:%S'),
        'started plotting read length distribution'))
    plot_read_lengths(read_length_counts, prefix)

    ### calculate metagene profiles
    now = datetime.datetime.now()
    print('{} ... {}'.format(
        now.strftime('%b %d %H:%M:%S'),
        'started calculating metagene profiles. This may take a long time...'))
    metagenes = metagene_coverage(annotated, alignments, read_length_counts,
                                  prefix)

    ### plot metagene profiles
    now = datetime.datetime.now()
    print('\n{} ... {}'.format(
        now.strftime('%b %d %H:%M:%S'), 'started plotting metagene profiles'))
    plot_metagene(metagenes, read_length_counts, prefix)

    ### align metagenes if psite_offsets not provided
    if psite_offsets is None:
        now = datetime.datetime.now()
        print('{} ... {}'.format(
            now.strftime('%b %d %H:%M:%S'),
            'started inferring P-site offsets'))
        psite_offsets = align_metagenes(metagenes, read_length_counts, prefix,
                                        read_lengths is None)

    ### merge read lengths based on P-sites offsets
    now = datetime.datetime.now()
    print('{} ... {}'.format(
        now.strftime('%b %d %H:%M:%S'),
        'started shifting according to P-site offsets'))
    merged_alignments = merge_read_lengths(alignments, psite_offsets)

    ### export wig file
    now = datetime.datetime.now()
    print('{} ... {}'.format(
        now.strftime('%b %d %H:%M:%S'),
        'started exporting wig file of alignments after shifting'))
    export_wig(merged_alignments, prefix)

    ### saving detecting results to disk
    now = datetime.datetime.now()
    print('{} ... {}'.format(
        now.strftime('%b %d %H:%M:%S'),
        'started calculating phase scores for each ORF'))
    export_orf_coverages(ribotricer_index, merged_alignments, prefix, report_all)
    now = datetime.datetime.now()
    print('{} ... {}'.format(
        now.strftime('%b %d %H:%M:%S'), 'finished ribotricer detect-orfs'))