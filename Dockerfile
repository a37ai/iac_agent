# Use the latest Miniconda3 base image
FROM continuumio/miniconda3:latest

# Set the working directory
WORKDIR /app

# Install essential build tools
RUN apt-get update && \
    apt-get install -y build-essential && \
    rm -rf /var/lib/apt/lists/*

# Update conda
RUN conda update -n base conda && \
    conda clean -afy

# Install mamba using conda-forge
RUN conda install mamba -n base -c conda-forge && \
    conda clean -afy

# Configure conda to prioritize conda-forge with strict priority
RUN conda config --add channels conda-forge && \
    conda config --set channel_priority strict && \
    conda clean -afy

# Copy the environment.yml first for better layer caching
COPY environment_droplet.yml /app/

# Copy the rest of the application code
COPY . /app

# Create the Conda environment using mamba and install dependencies
RUN mamba env create -f environment_droplet.yml --yes && \
    conda run -n forge_pipeline pip install --upgrade pip && \
    conda run -n forge_pipeline pip install -e . && \
    conda clean -afy

# Use SHELL to ensure subsequent commands run within the conda environment
SHELL ["conda", "run", "-n", "forge_pipeline", "/bin/bash", "-c"]

# Set the default command to bash
CMD ["bash"]
