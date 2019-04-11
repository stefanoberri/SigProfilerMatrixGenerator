#!/usr/bin/env python3
 
#Author: Erik Bergstrom

#Contact: ebergstr@eng.ucsd.edu

from . import SigProfilerMatrixGenerator as matGen
import os
import re
import sys
import pandas as pd
import datetime
from SigProfilerMatrixGenerator.scripts import convert_input_to_simple_files as convertIn
import uuid
import shutil
import time
import numpy as np
import itertools
from pathlib import Path

def perm(n, seq):
	'''
	Generates a list of all available permutations of n-mers.

	Parameters:
			   n  -> length of the desired permutation string
			 seq  -> list of all possible string values

	Returns:
		  permus  -> list of all available permutations
	'''
	permus = []
	for p in itertools.product(seq, repeat=n):
		permus.append("".join(p))
	return(permus)



def SigProfilerMatrixGeneratorFunc (project, genome, vcfFiles, exome=False, bed_file=None, chrom_based=False, plot=False, tsb_stat=False, seqInfo=False, gs=False):
	'''
	Allows for the import of the sigProfilerMatrixGenerator.py function. Returns a dictionary
	with each context serving as the first level of keys. 

	Parameters:
			   	  project  -> unique name given to the current samples
				   genome  -> reference genome 
				 vcfFiles  -> path where the input vcf files are located.
				 	exome  -> flag to use only the exome or not
			  	 bed_file  -> BED file that contains a list of ranges to be used in generating the matrices
			  chrom_based  -> flag to create the matrices on a per chromosome basis
			  		 plot  -> flag to generate the plots for each context
			  	 tsb_stat  -> performs a transcriptional strand bias test for the 24, 384, and 6144 contexts. The output is
			  		  		  saved into the output/TSB directory
			  		   gs  -> flag that performs a gene strand bias test

	Returns:
			  	 matrices  -> dictionary (nested) of the matrices for each context

		example:
			matrices = {'96': {'PD1001a':{'A[A>C]A':23,
										 'A[A>G]A':10,...},
							  'PD1202a':{'A[A>C]A':23,
										 'A[A>G]A':10,...},...},
						'192':{'PD1001a':{'T:A[A>C]A':23,
										 'T:A[A>G]A':10,...},
							  'PD1202a':{'T:A[A>C]A':23,
										 'T:A[A>G]A':10,...},...},...}
	'''

	# Instantiates all of the required variables and references
	if gs:
		print("The Gene Strand Bias is not yet supported! Continuing with the matrix generation.")
		gs = False
	functionFlag = True
	bed = False
	bed_ranges = None
	limited_indel = True
	exome = exome
	plot = plot


	# Instantiates the final output matrix
	matrices = {'96':None, '1536':None, '384':None, '6144':None, 'DINUC':None, '6':None, '24':None, 'INDEL':None}

	# Provides a chromosome conversion from NCBI notation
	ncbi_chrom = {'NC_000067.6':'1', 'NC_000068.7':'2', 'NC_000069.6':'3', 'NC_000070.6':'4', 
				  'NC_000071.6':'5', 'NC_000072.6':'6', 'NC_000073.6':'7', 'NC_000074.6':'8',
				  'NC_000075.6':'9', 'NC_000076.6':'10', 'NC_000077.6':'11', 'NC_000078.6':'12',
				  'NC_000079.6':'13', 'NC_000080.6':'14', 'NC_000081.6':'15', 'NC_000082.6':'16', 
				  'NC_000083.6':'17', 'NC_000084.6':'18', 'NC_000085.6':'19', 'NC_000086.7':'X', 
				  'NC_000087.7':'Y'}

	# Provides the reference file conversion from binary to base information			  
	tsb_ref = {0:['N','A'], 1:['N','C'], 2:['N','G'], 3:['N','T'],
			   4:['T','A'], 5:['T','C'], 6:['T','G'], 7:['T','T'],
			   8:['U','A'], 9:['U','C'], 10:['U','G'], 11:['U','T'],
			   12:['B','A'], 13:['B','C'], 14:['B','G'], 15:['B','T'],
			   16:['N','N'], 17:['T','N'], 18:['U','N'], 19:['B','N']}

	bias_sort = {'T':0,'U':1,'N':3,'B':2}
	tsb = ['T','U','N','B']
	bases = ['A','C','G','T']
	mutation_types = ['AC>CA','AC>CG','AC>CT','AC>GA','AC>GG','AC>GT','AC>TA','AC>TG','AC>TT',
					  'AT>CA','AT>CC','AT>CG','AT>GA','AT>GC','AT>TA','CC>AA','CC>AG','CC>AT',
					  'CC>GA','CC>GG','CC>GT','CC>TA','CC>TG','CC>TT','CG>AT','CG>GC','CG>GT',
					  'CG>TA','CG>TC','CG>TT','CT>AA','CT>AC','CT>AG','CT>GA','CT>GC','CT>GG',
					  'CT>TA','CT>TC','CT>TG','GC>AA','GC>AG','GC>AT','GC>CA','GC>CG','GC>TA',
					  'TA>AT','TA>CG','TA>CT','TA>GC','TA>GG','TA>GT','TC>AA','TC>AG','TC>AT',
					  'TC>CA','TC>CG','TC>CT','TC>GA','TC>GG','TC>GT','TG>AA','TG>AC','TG>AT',
					  'TG>CA','TG>CC','TG>CT','TG>GA','TG>GC','TG>GT','TT>AA','TT>AC','TT>AG',
					  'TT>CA','TT>CC','TT>CG','TT>GA','TT>GC','TT>GG']

	# Pre-fills the mutation types variable
	size = 5
	mut_types_initial = perm(size, "ACGT")
	mut_types = []
	for tsbs in tsb:
		for mut in mut_types_initial:
			current_base = mut[int(size/2)]
			if current_base == 'C' or current_base == 'T':
				for base in bases:
					if base != current_base:
						mut_types.append(tsbs+":"+mut[0:int(size/2)] + "[" + current_base+">"+ base+"]"+mut[int(size/2)+1:])

	# Organizes all of the mutation types for DINUCs
	mutation_types_tsb_context = []
	for base in bases:
		for mut in mutation_types:
			for base2 in bases:
				for base3 in tsb:
					mutation_types_tsb_context.append(''.join([base3,":",base,"[",mut,"]",base2]))
					mut_tsb = base3 + ":" + mut

	indel_types_tsb = []
	indel_types_simple = []

	indel_types = ['1:Del:C:0', '1:Del:C:1', '1:Del:C:2', '1:Del:C:3', '1:Del:C:4', '1:Del:C:5',
				   '1:Del:T:0', '1:Del:T:1', '1:Del:T:2', '1:Del:T:3', '1:Del:T:4', '1:Del:T:5',
				   '1:Ins:C:0', '1:Ins:C:1', '1:Ins:C:2', '1:Ins:C:3', '1:Ins:C:4', '1:Ins:C:5',
				   '1:Ins:T:0', '1:Ins:T:1', '1:Ins:T:2', '1:Ins:T:3', '1:Ins:T:4', '1:Ins:T:5', 
						# >1bp INDELS
				   '2:Del:R:0', '2:Del:R:1', '2:Del:R:2', '2:Del:R:3', '2:Del:R:4', '2:Del:R:5',
				   '3:Del:R:0', '3:Del:R:1', '3:Del:R:2', '3:Del:R:3', '3:Del:R:4', '3:Del:R:5',
				   '4:Del:R:0', '4:Del:R:1', '4:Del:R:2', '4:Del:R:3', '4:Del:R:4', '4:Del:R:5',
				   '5:Del:R:0', '5:Del:R:1', '5:Del:R:2', '5:Del:R:3', '5:Del:R:4', '5:Del:R:5',
				   '2:Ins:R:0', '2:Ins:R:1', '2:Ins:R:2', '2:Ins:R:3', '2:Ins:R:4', '2:Ins:R:5', 
				   '3:Ins:R:0', '3:Ins:R:1', '3:Ins:R:2', '3:Ins:R:3', '3:Ins:R:4', '3:Ins:R:5', 
				   '4:Ins:R:0', '4:Ins:R:1', '4:Ins:R:2', '4:Ins:R:3', '4:Ins:R:4', '4:Ins:R:5',
				   '5:Ins:R:0', '5:Ins:R:1', '5:Ins:R:2', '5:Ins:R:3', '5:Ins:R:4', '5:Ins:R:5',
						#MicroHomology INDELS
				   '2:Del:M:1', '3:Del:M:1', '3:Del:M:2', '4:Del:M:1', '4:Del:M:2', '4:Del:M:3',
				   '5:Del:M:1', '5:Del:M:2', '5:Del:M:3', '5:Del:M:4', '5:Del:M:5', '2:Ins:M:1', 
				   '3:Ins:M:1', '3:Ins:M:2', '4:Ins:M:1', '4:Ins:M:2', '4:Ins:M:3', '5:Ins:M:1', 
				   '5:Ins:M:2', '5:Ins:M:3', '5:Ins:M:4', '5:Ins:M:5', 'complex', 'non_matching']

	for indels in indel_types[:24]:
		for tsbs in tsb:
			indel_types_tsb.append(tsbs + ":" + indels)

	indel_types_simple = indel_types[:24]
	indel_types_simple.append('long_Del')
	indel_types_simple.append('long_Ins')
	indel_types_simple.append('MH')
	indel_types_simple.append('complex')
	# Instantiates the initial contexts to generate matrices for
	contexts = ['6144']#, 'DINUC']

	# Organizes all of the reference directories for later reference:
	current_dir = os.path.realpath(__file__)
	# current_dir = Path(os.path.realpath(__file__))
	# ref_dir = Path(*current_dir.parent.parts[:-1])

	ref_dir = re.sub('\/scripts/SigProfilerMatrixGeneratorFunc.py$', '', current_dir)
	chrom_path =ref_dir + '/references/chromosomes/tsb/' + genome + "/"
	transcript_path = ref_dir + '/references/chromosomes/transcripts/' + genome + "/"
	# chrom_path = ref_dir / 'references/chromosomes/tsb/' / genome
	# transcript_path = ref_dir / 'references/chromosomes/transcripts/' / genome


	#print(ref_dir, chrom_path, transcript_path)
	# Terminates the code if the genome reference files have not been created/installed
	if not os.path.exists(chrom_path):
		print("The specified genome: " + genome + " has not been installed\nRun the following command to install the genome:\n\tpython3 sigProfilerMatrixGenerator/install.py -g " + genome)
		sys.exit()

	# Organizes all of the input and output directories:
	if vcfFiles[-1] != "/":
		vcfFiles += "/"
	vcf_path = vcfFiles + "input/"
	# vcfFiles = Path(vcfFiles)
	# vcf_path = vcfFiles / "input"

	vcf_path_original = vcf_path
	if not os.path.exists(vcf_path) or len(os.listdir(vcf_path)) < 1:
		os.makedirs(vcf_path, exist_ok=True)
		input_files = os.listdir(vcfFiles)
		if os.path.exists(vcfFiles + "input/"):
			input_files.remove("input")
		if os.path.exists(vcfFiles + "logs/"):
			input_files.remove("logs")
		if ".DS_Store" in input_files:
			input_files.remove(".DS_Store")
		if "__init__.py" in input_files:
			input_files.remove("__init__.py")
		if "__pycache__" in input_files:
			input_files.remove("__pycache__")
		for files in input_files:
			shutil.copy(vcfFiles + files, vcf_path + files)
	output_matrix = vcfFiles + "output/"
	#output_matrix = vcfFiles / "output"

	if not os.path.exists(output_matrix):
		os.system("mkdir " + output_matrix)


	# Organizes the error and log files
	time_stamp = datetime.date.today()
	output_log_path = vcfFiles + "logs/"
	if not os.path.exists(output_log_path):
		os.system("mkdir " + output_log_path)
	error_file = output_log_path + 'SigProfilerMatrixGenerator_' + project + "_" + genome + str(time_stamp) + ".err"
	log_file = output_log_path + 'SigProfilerMatrixGenerator_' + project + "_" + genome + str(time_stamp) + ".out"

	if os.path.exists(error_file):
		os.system("rm " + error_file)
	if os.path.exists(log_file):
		 os.system("rm " + log_file)
	sys.stderr = open(error_file, 'w')
	#out = open(log_file, 'w')



	# Gathers all of the vcf files:
	vcf_files_temp = os.listdir(vcf_path)
	vcf_files = []
	first_extenstion = True
	for file in vcf_files_temp:
		# Skips hidden files
		if file[0:3] == '.DS' or file[0:2] == '__':
			pass
		else:
			vcf_files.append(file)

	# Creates a temporary folder for sorting and generating the matrices
	file_name = vcf_files[0].split(".")
	file_extension = file_name[-1]
	unique_folder = project + "_"+ str(uuid.uuid4())
	output_path = output_matrix + "temp/" + unique_folder + "/"
	if os.path.exists(output_path):
		os.system("rm -r " + output_path)
	os.makedirs(output_path)

	skipped_muts = 0
	# Converts the input files to standard text in the temporary folder
	if file_extension == 'genome':
			snv, indel, skipped, samples = convertIn.convertTxt(project, vcf_path, genome, output_path)
	else:
		if file_extension == 'txt':
			snv, indel, skipped, samples = convertIn.convertTxt(project, vcf_path,  genome,  output_path, ncbi_chrom, log_file)
		elif file_extension == 'vcf':
			snv, indel, skipped, samples = convertIn.convertVCF(project, vcf_path,  genome, output_path, ncbi_chrom, log_file)
		elif file_extension == 'maf':
			snv, indel, skipped, samples = convertIn.convertMAF(project, vcf_path,  genome, output_path, ncbi_chrom, log_file)
		elif file_extension == 'tsv':
			snv, indel, skipped, samples = convertIn.convertICGC(project, vcf_path,  genome, output_path, ncbi_chrom, log_file)
		else:
			print("File format not supported")

	skipped_muts += skipped
	
	# Instantiates variables for final output statistics
	analyzed_muts = [0, 0, 0]
	
	sample_count_high = 0


	# Begins matrix generation for all possible contexts
	for i in range(0, 2, 1):
		if i == 0 and snv:
			mutation_pd = {}
			mutation_pd['6144'] = pd.DataFrame(0, index=mut_types, columns=samples)

			output_path_snv = output_path + "SNV/"
			vcf_files = os.listdir(output_path_snv)
			vcf_path = output_path_snv
			print("Starting matrix generation for SNVs and DINUCs...", end='', flush=True)
			start = time.time()

		# Skips SNVs if none are present
		elif i == 0 and not snv:
			continue
		elif i == 1 and indel:
			mutation_ID = {}
			mutation_ID['ID'] = pd.DataFrame(0, index=indel_types, columns=samples)
			mutation_ID['simple'] = pd.DataFrame(0, index=indel_types_simple, columns=samples)
			mutation_ID['tsb'] = pd.DataFrame(0, index=indel_types_tsb, columns=samples)

			contexts = ['INDEL']
			output_path_indel = output_path + "INDEL/"
			vcf_files = os.listdir(output_path_indel)
			vcf_path = output_path_indel
			print("Starting matrix generation for INDELs...", end='', flush=True)
			start = time.time()

		# Skips INDELs if none are present and deletes the temp folder
		elif i ==1 and not indel:
			os.system("rm -r " + output_matrix + "temp/")
			continue

		# Removes hidden files generated in macos
		if ".DS_Store" in vcf_files:
			vcf_files.remove(".DS_Store")


		# Generates the bed regions if a bed file was provided
		if bed_file != None:
			bed = True
			bed_file_path = bed_file
			bed_ranges = matGen.BED_filtering(bed_file_path)
		else:
			bed_file_path = None

		# Sorts files based on chromosome, sample, and start position
		#zeros = np.zeros(len(mut_types))
		first_chrom = True
		first_dinuc = True
		#mutation_pd = pd.DataFrame(index=mut_types)
		if not chrom_based:
			chrom_start = None
		if i != 1:
			for file in vcf_files:
				dinuc = True
				chrom = file.split("_")[0]
				with open(vcf_path + file) as f:
					lines = [line.strip().split() for line in f]
				lines = sorted(lines, key = lambda x: (x[0], int(x[2])))


				context = '6144'
				mutation_pd, skipped_mut, total, total_DINUC, all_dinucs = matGen.catalogue_generator_single (lines, chrom, mutation_pd, mutation_types_tsb_context, vcf_path, vcf_path_original, vcf_files, bed_file_path, chrom_path, project, output_matrix, context, exome, genome, ncbi_chrom, functionFlag, bed, bed_ranges, chrom_based, plot, tsb_ref, transcript_path, tsb_stat, seqInfo, gs, log_file)
				
				if not any(all_dinucs):
					dinuc = False

				if first_chrom:
					#mutation_pd = pd.DataFrame.from_dict(mutation_dict)
					if dinuc:
						mutation_dinuc_pd_all = pd.DataFrame.from_dict(all_dinucs)
						first_dinuc = False
					first_chrom = False
				else:
					#mutation_pd = mutation_pd.add(pd.DataFrame.from_dict(mutation_dict), fill_value=0)
					if dinuc:
						if first_dinuc:
							mutation_dinuc_pd_all = pd.DataFrame.from_dict(all_dinucs)
							first_dinuc = False
						else:
							mutation_dinuc_pd_all = mutation_dinuc_pd_all.add(pd.DataFrame.from_dict(all_dinucs), fill_value=0)

				#mutation_pd = mutation_pd.fillna(0)


				skipped_muts += skipped_mut
				analyzed_muts[0] += total
				analyzed_muts[1] += total_DINUC
			#sample_count_high = len(list(mutation_pd.columns.values))	

			sample_count_high = len(samples)	

		#if i != 1:
			if exome:
				with open(vcf_path + "exome_temp.txt") as f:
					lines = [line.strip().split() for line in f]
				output = open(vcf_path + "exome_temp.txt", 'w')
				for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
					print('\t'.join(line), file=output)
				output.close()
				mutation_mat, samples2 = matGen.exome_check(genome, vcf_path + "exome_temp.txt", output_matrix, project, "SNV")
				mutation_pd['6144'] = pd.DataFrame.from_dict(mutation_mat)
				mutation_pd['6144'] = mutation_pd['6144'].fillna(0)

			if bed:
				with open(vcf_path + "bed_temp.txt") as f:
					lines = [line.strip().split() for line in f]
				output = open(vcf_path + "bed_temp.txt", 'w')
				for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
					print('\t'.join(line), file=output)
				output.close()
				mutation_mat, samples2 = matGen.panel_check(genome, vcf_path + "bed_temp.txt", output_matrix, bed_file_path, project, "SNV")
				mutation_pd['6144'] = pd.DataFrame.from_dict(mutation_mat)
				mutation_pd['6144'] = mutation_pd['6144'].fillna(0)

			if not mutation_pd['6144'].empty:
				matrices = matGen.matrix_generator (context, output_matrix, project, samples, bias_sort, mutation_pd, exome, mut_types, bed, chrom_start, functionFlag, plot, tsb_stat)
			
			if analyzed_muts[1] > 0:
				if exome:
					with open(vcf_path + "exome_temp_context_tsb_DINUC.txt") as f:
						lines = [line.strip().split() for line in f]
					output = open(vcf_path + "exome_temp_context_tsb_DINUC.txt", 'w')
					for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
						print('\t'.join(line), file=output)
					output.close()

					all_dinucs, samples2 = matGen.exome_check(genome, vcf_path + "exome_temp_context_tsb_DINUC.txt", output_matrix, project, "DINUC")
					mutation_dinuc_pd_all = pd.DataFrame.from_dict(all_dinucs)

				if bed:
					with open(vcf_path + "bed_temp_context_tsb_DINUC.txt") as f:
						lines = [line.strip().split() for line in f]
					output = open(vcf_path + "bed_temp_context_tsb_DINUC.txt", 'w')
					for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
						print('\t'.join(line), file=output)
					output.close()

					all_dinucs, samples2 = matGen.panel_check(genome, vcf_path + "bed_temp_context_tsb_DINUC.txt", output_matrix, bed_file_path, project, "DINUC")
					mutation_dinuc_pd_all = pd.DataFrame.from_dict(all_dinucs)

				if not mutation_dinuc_pd_all.empty:
					dinuc_mat = matGen.matrix_generator_DINUC (output_matrix, samples, bias_sort, mutation_dinuc_pd_all, mutation_types_tsb_context, project, exome, bed, chrom_start, plot)
					matrices['DINUC'] = dinuc_mat

		else:
			for file in vcf_files:
				chrom = file.split("_")[0]
				with open(vcf_path + file) as f:
					lines = [line.strip().split() for line in f]
				lines = sorted(lines, key = lambda x: (x[0], int(x[2])))			
				mutation_ID, skipped_mut, total = matGen.catalogue_generator_INDEL_single (mutation_ID, lines, chrom, vcf_path, vcf_path_original, vcf_files, bed_file_path, chrom_path, project, output_matrix, exome, genome, ncbi_chrom, limited_indel, functionFlag, bed, bed_ranges, chrom_based, plot, tsb_ref, transcript_path, seqInfo, gs, log_file)
				skipped_muts += skipped_mut
				analyzed_muts[2] += total

			# Performs the final filter on the variants base upon the exome if desired
			if exome:
				with open(vcf_path + "exome_temp.txt") as f:
					lines = [line.strip().split() for line in f]
				output = open(vcf_path + "exome_temp.txt", 'w')
				for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
					print('\t'.join(line), file=output)
				output.close()

				indel_dict, samples2 = matGen.exome_check(genome, vcf_path + "exome_temp.txt", output_matrix, project, "INDEL", '83')
				mutation_ID['ID'] = pd.DataFrame.from_dict(indel_dict)

				with open(vcf_path + "exome_temp_simple.txt") as f:
					lines = [line.strip().split() for line in f]
				output = open(vcf_path + "exome_temp_simple.txt", 'w')
				for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
					print('\t'.join(line), file=output)
				output.close()

				indel_dict, samples2 = matGen.exome_check(genome, vcf_path + "exome_temp_simple.txt", output_matrix, project, "INDEL", 'simple')
				mutation_ID['simple'] = pd.DataFrame.from_dict(indel_dict)


				with open(vcf_path + "exome_temp_tsb.txt") as f:
					lines = [line.strip().split() for line in f]
				output = open(vcf_path + "exome_temp_tsb.txt", 'w')
				for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
					print('\t'.join(line), file=output)
				output.close()

				indel_dict, samples2 = matGen.exome_check(genome, vcf_path + "exome_temp.txt", output_matrix, project, "INDEL", 'tsb')
				mutation_ID['tsb'] = pd.DataFrame.from_dict(indel_dict)

			if bed:
				with open(vcf_path + "bed_temp.txt") as f:
					lines = [line.strip().split() for line in f]
				output = open(vcf_path + "bed_temp.txt", 'w')
				for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
					print('\t'.join(line), file=output)
				output.close()
				indel_dict, samples2 = matGen.panel_check(genome, vcf_path + "bed_temp.txt", output_matrix, bed_file_path, project, "INDEL", '83')
				mutation_ID['ID'] = pd.DataFrame.from_dict(indel_dict)

				with open(vcf_path + "bed_temp_simple.txt") as f:
					lines = [line.strip().split() for line in f]
				output = open(vcf_path + "bed_temp_simple.txt", 'w')
				for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
					print('\t'.join(line), file=output)
				output.close()
				indel_dict, samples2 = matGen.panel_check(genome, vcf_path + "bed_temp_simple.txt", output_matrix, bed_file_path, project, "INDEL", 'simple')
				mutation_ID['simple'] = pd.DataFrame.from_dict(indel_dict)

				with open(vcf_path + "bed_temp_tsb.txt") as f:
					lines = [line.strip().split() for line in f]
				output = open(vcf_path + "bed_temp_tsb.txt", 'w')
				for line in sorted(lines, key = lambda x: (['X','Y','1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', 'MT', 'M'].index(x[1]), int(x[2]))):
					print('\t'.join(line), file=output)
				output.close()
				indel_dict, samples2 = matGen.panel_check(genome, vcf_path + "bed_temp_tsb.txt", output_matrix, bed_file_path, project, "INDEL", 'tsb')
				mutation_ID['tsb'] = pd.DataFrame.from_dict(indel_dict)


			mutation_ID['ID'] = mutation_ID['ID'].to_dict('dict')
			mutation_ID['simple'] = mutation_ID['simple'].to_dict('dict')
			mutation_ID['tsb'] = mutation_ID['tsb'].to_dict('dict')
			matGen.matrix_generator_INDEL(output_matrix, samples, indel_types, indel_types_tsb, indel_types_simple, mutation_ID['ID'], mutation_ID['tsb'], mutation_ID['simple'], project, exome, limited_indel, bed, chrom_start, plot)

		if i == 1:
			os.system("rm -r " + output_matrix + "temp/")
		end = time.time() - start
		print("Completed! Elapsed time: " + str(round(end, 2)) + " seconds.")

	# Prints a summary for the given run (total samples, skipped mutations, etc.)
	if not chrom_based:
		print("Matrices generated for " + str(sample_count_high) + " samples with " + str(skipped_muts) + " errors. Total of " + str(analyzed_muts[0]) + " SNVs, " + str(analyzed_muts[1]) + " DINUCs, and " + str(analyzed_muts[2]) + " INDELs were successfully analyzed.")
	return(matrices)

	