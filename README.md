# Robust detection of actively translating ORFs from Ribo-seq data

## Installation
We highly recommend that you install RiboCop via conda
```bash
conda install -c bioconda ribocop
```

------------------

## Workflow of RiboCop

In order to run RiboCop, you need to have the following three files
prepared including:
* **genome annotation file** in GTF format, supporting both GENCODE and
Ensembl annotation
* **reference genome file** in FASTA format
* **alignment file** in BAM format

### Prepare candidate ORFs
The first step of RiboCop is to take the GTF file and the FASTA file to find all
candidate ORFs. In order to generate all candidate ORFs, please run
```bash
RiboCop prepare-orfs --gtf {GTF} --fasta {FASTA} --prefix {PREFIX}
```
The command above by default only includes ORFs with length longer than 60 nts,
and only uses 'ATG' as start codon. You can change the setting by including
options ```--min_orf_length``` and ```--start_codons```.  
Output: {PREFIX}\_candidate\_orfs.tsv.

### Detecting translating ORFs
The second step of RiboCop is to take the index file generated by ```prepare-orfs```
and the BAM file to detect the actively translating ORFs by assessing the periodicity
of all candidate ORFs:
```bash
RiboCop detect-orfs --bam {BAM} --ribocop_index {PREFIX}_candidate_ORFs.tsv --prefix {PREFIX}
```
The ORF detection step consists of several small steps including:
1. Infer the experimental protocol (strandedness of the reads)  
You can directly assign the strandedness using option ```--stranded```, it can be 'yes',
'no', or 'reverse'. If this option is not provided, RiboCop will automatically infer the
experimental protocol by comparing the strand of reads to the reference.   
Output: {PREFIX}\_protocol.txt
2. Split the bam file by strand and read length  
In this step, all mapped reads will be filtered to include only uniquely mapped reads. Reads
will be split by strand and read length with respect to the strandedness provided or inferred
from the previous step. If you only want to include certain read lengths, they can be assigned with
option ```--read_lengths```.  
Output: {PREFIX}\_bam\_summary.txt
3. Plot read length distribution  
In this step, read length distribution will be plotted and serves as quality control  
Output: {PREFIX}\_read\_length\_dist.pdf
4. Calculate metagene profiles  
In this step, the metagene profile of all CDS transcripts for each read length is
calculated by aligning with start codon or stop codon.  
Output: {PREFIX}\_metagene\_profiles\_5p.tsv is the metagene profile aligning with the
start codon and {PREFIX}\_metagene\_profiles\_3p.tsv is the metagene profile aligning with
the stop codon
5. Plot metagene profiles  
In this step, metagene plots will be made to serve as quality control.  
Output: {PREFIX}\_metagene\_plots.pdf
6. Align metagene profiles
If the P-site offsets are not provided, this step will use cross-correlation to find out the relative
offsets between different read lengths  
Output: {PREFIX}\_psite\_offsets.txt
7. merge reads from different read lengths based on P-site offsets
This step will integrate reads of different read lengths by shifting with the P-site offsets 
8. Export wig file
A WIG file is exported in this step to be used for visualization in Genome Browser  
Output: {PREFIX}\_pos.wig for the positive strand and {PREFIX}\_neg.wig for the negative strand.
9. Export actively translating ORFs
The periodicity of all ORF profiles are assessed and the translating ones are outputed. You can output all ORFs regardless
of the translation status with option ```--report_all```  
Output: {PREFIX}\_translating\_ORFs.tsv
    
------------------

## Contacts and bug reports
Andrew D. Smith
andrewds@usc.edu

Wenzheng Li
wenzhenl@usc.edu

Saket Choudhary
skchoudh@usc.edu

We are dedicated to make the best ORF detector for Ribo-seq data analysis.
If you found a bug or mistake in this project, we would like to know about it.
Before you send us the bug report though, please check the following:

1. Are you using the latest version? The bug you found may already have been
   fixed.
2. Check that your input is in the correct format and you have selected the
   correct options.
3. Please reduce your input to the smallest possible size that still produces
   the bug; we will need your input data to reproduce the problem, and the
   smaller you can make it, the easier it will be.
   
------------------

## LICENSE
RiboCop for detecting actively translating ORFs from Ribo-seq data
Copyright (C) 2018 Andrew D Smith, Wenzheng Li, Saket Choudhary and
the University of Southern California

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or (at
your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
