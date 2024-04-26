# DBF Test runner

This script provides a parallelized wrapper for running DBF Test on a VCF containing biallelic variants.

## Installing

It is recommended to install this script in a virtual environment:

    $ python3 -m venv .venv
    $ . .venv/bin/activate.sh
    $ python3 -m pip install .
    $ dbf_test --help

This script expects the `DBF_test.R` script (see below) to be located in the current working directory. This can be overridden by using the `--dbf-test-script` argument or by setting the `DBF_TEST_SCRIPT` environment variable:

    # Option 1: DBF_test.R is located in the current working directory:
    $ ls
    DBF_test.R  data.vcf  data.csv
    $ dbf_test --genotypes data.vcf --distance-matrix data.csv

    # Option 2: Manually specify the location of DBF_test.R:
    $ dbf_test --genotypes data.vcf --distance-matrix data.csv --dbf-test-script /path/to/DBF_test.R

    # Option 3: Export the DBF_TEST_SCRIPT variable (for example in your ~/.bashrc)
    $ export DBF_TEST_SCRIPT="/path/to/DBF_test.R"
    $ ls
    data.vcf  data.csv
    $ dbf_test --genotypes data.vcf --distance-matrix data.csv

## Obtaining DBF_test.R

A version of the script corresponding to the 2014 publication can be found at https://github.com/mruehlemann/DBF_test. The license for this version is unspecified.

    Minas, C. and Montana, G. (2014), Distance-based analysis of variance: Approximate inference†. Statistical Analy Data Mining, 7: 450-470. https://doi.org/10.1002/sam.11227

Alternatively, an archived CRAN package can be found at https://cran.r-project.org/web/packages/DBFTest/index.html, licensed under the GPLv2. Note that this package is broken and a workaround was implemented in the `Worker._work` function to allow this version to be used.

    Minas, C., Waddell, S. J. and Montana, G. (2011). Distance-based differential analysis of gene curves. Bioinformatics

    Minas, C. and Montana, G. (2012). Distance-based analysis of variance: approximate inference. Submitted to Statistical Analysis and Data Mining. arxiv: http://arxiv.org/abs/1205.2417

Test statistics appear to be identical between the two versions, but p-values differ.

## Usage

    usage: dbf_test [-h] [-v] [--threads N] --distance-matrix CSV --genotypes VCF
                    [--dbf-test-script PATH] [--name-mapping CSV]
                    [--name-column-matrix NAME_COLUMN_MATRIX]
                    [--name-column-genotypes NAME_COLUMN_GENOTYPES] [--permissive]
                    [--min-r2 R2] [--min-maf MAF] [--positions] [--head N]

    options:
    -h, --help            show this help message and exit
    -v, --version         Display script version
    --threads N           Number of worker threads used to compute the DBF test
                            statistic (default: 1)
    --dbf-test-script PATH
                            Path to the `DBF_test.R` script; defaults to the same
                            folder as this script (default: DBF_test.R)

    Input files:
    --distance-matrix CSV
                            Path to distance matrix for samples in the VCF file;
                            the matrix is expected to be comma-separated and have
                            both row and column names. The matrix must include all
                            sample names in the VCF but may also contain samples
                            not found in the VCF (default: None)
    --genotypes VCF       VCF files containing sample genotypes. Sample names
                            must either match the names in the distance matrix or a
                            name mapping file must be supplied with --name-mapping
                            (default: None)

    Sample information:
    --name-mapping CSV    Path to CSV containing a column with the sample names
                            in the distance matrix and a column containing the
                            names in the vcf file. If this file is not specified,
                            then the names in the distance matrix and VCF must be
                            identical (default: None)
    --name-column-matrix COLUMN
                            The name of the column in the --name-mapping file
                            containing the names used in the --distance-matrix CSV
                            file (default: SampleID)
    --name-column-genotypes COLUMN
                            The name of the column in the --name-mapping file
                            containing the names used in the --genotypes VCF file
                            (default: IND_ID)

    Site filtering:
    --permissive          Skip sites containing non-biallelic genotypes or
                            missing R2 or MAF scores. By default this script will
                            terminate if such a site is found (default: False)
    --min-r2 R2           Require a per-site R2 value > the specified value
                            (default: 0.4)
    --min-maf MAF         Require a per-site MAF value >= the specified value
                            (default: 0.01)

    Misc:
    --positions           Include CHROM and POS columns in output (default:
                            False)
    --head N              Return only the first N results (default: None)


## Example

The `examples` folder contains a simple example that demonstrates how to run `dbf_test`.

If sample names in the VCF and the distance matrix match:

    $ dbf_test --genotypes example.same_names.vcf --distance-matrix example.matrix.csv

If sample names in the VCF and the distance matrix differ and a mapping is required:

    $ dbf_test --genotypes example.same_names.vcf --distance-matrix example.matrix.csv --name-mapping example.names.csv

The exact results will depend on the version of `DBF_test.R` used.

If using the mruehlemann/DBF_test version:

    SNP  A1  A2  A2_FREQ  ALL_MAF  R2   STAT                 P
    .    A   T   0.5      0.2      0.7  0.14046208449706218  0.02871265456530825

If using the CRAN release:

    SNP  A1  A2  A2_FREQ  ALL_MAF  R2   STAT                 P
    .    A   T   0.5      0.2      0.7  0.14046208449706218  0.030303030303030304

Note that this output has been reformatted for readability.
