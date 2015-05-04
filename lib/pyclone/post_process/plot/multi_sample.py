'''
Created on 2013-06-06

@author: Andrew Roth
'''
from __future__ import division

from collections import OrderedDict
from eppl.parallel_coordinates import aggregated_parallel_coordinates_plot, parallel_coordinates_plot

import csv
import os
import yaml

try:
    import matplotlib.pyplot as plot
except:
    raise Exception("The multi sample plotting module requires the matplotlib package. See http://matplotlib.org.")

try:
    import pandas as pd
except:
    raise Exception("The multi sample plotting module requires the pandas package. See http://http://pandas.pydata.org.")

from pyclone.config import load_mutation_from_dict
from pyclone.post_process.cluster import cluster_pyclone_trace
from pyclone.post_process.utils import load_cellular_frequencies_trace

def plot_clusters(config_file, plot_file, prevalence, clustering_method, burnin, thin):
    data = load_multi_sample_table(config_file, prevalence, clustering_method, burnin, thin)
    
    if prevalence == 'cellular':
        plot_data, error_data = _load_plot_data(config_file, data, get_error_data=True)
    
    else:
        plot_data, error_data = _load_plot_data(config_file, data, get_error_data=False)
    
    fig = plot.figure()
    
    ax = fig.add_subplot(1, 1, 1)
    
    title = 'Cluster {0} Prevalence by Sample'.format(prevalence.capitalize())

    aggregated_parallel_coordinates_plot(plot_data,
                                         'cluster_id',
                                         ax=ax,
                                         show_class_size=True,
                                         title=title,
                                         x_label='Sample',
                                         y_label='Prevalence',
                                         error_data=error_data)
    
    ax.set_ylim(0, 1.0)
    
    ax.legend_.set_title('Cluster')
    
    fig.savefig(plot_file, dpi=600)

def plot_mutations(config_file, plot_file, prevalence, clustering_method, burnin, thin):
    data = load_multi_sample_table(config_file, prevalence, clustering_method, burnin, thin)
    
    if prevalence == 'cellular':
        plot_data, error_data = _load_plot_data(config_file, data, get_error_data=True)
    
    else:
        plot_data, error_data = _load_plot_data(config_file, data, get_error_data=False)
        
    fig = plot.figure()
    
    ax = fig.add_subplot(1, 1, 1)
    
    title = 'Mutation {0} Prevalence by Sample'.format(prevalence.capitalize())
    
    parallel_coordinates_plot(plot_data,
                              'cluster_id',
                              ax=ax,
                              title=title,
                              x_label='Sample',
                              y_label='Prevalence',
                              error_data=error_data)
    
    ax.set_ylim(0, 1.0)
    
    ax.legend_.set_title('Cluster')
    
    fig.savefig(plot_file, dpi=600)

def _load_yaml_config(file_name):
    fh = open(file_name)
    
    config = yaml.load(fh)
    
    fh.close()
    
    return config

def load_multi_sample_table(config_file, prevalence, clustering_method, burnin, thin):
    config = _load_yaml_config(config_file)
    
    if prevalence == 'allelic':
        data = _load_allelic_prevalences(config)
    
    elif prevalence == 'cellular':
        data = _load_cellular_prevalences(config, burnin, thin)
    
    trace_dir = os.path.join(config['working_dir'], config['trace_dir'])
    
    labels_file = os.path.join(trace_dir, 'labels.tsv.bz2')
    
    labels = cluster_pyclone_trace(labels_file, clustering_method, burnin, thin)
    
    for mutation_id, cluster_id in labels.items():
        data[mutation_id]['cluster_id'] = cluster_id
    
    data = pd.DataFrame(data)
    
    data = data.T
    
    data.cluster_id = data.cluster_id.astype(int)
    
    return data 

#=======================================================================================================================
# Load allelic prevalences for all samples
#=======================================================================================================================
def _load_allelic_prevalences(config):
    all_data = OrderedDict()
    
    if 'pyclone' in config['density']:
        mutations_file_format = 'yaml'
    
    else:
        mutations_file_format = 'tsv'
    
    for sample_id in config['samples']:
        file_name = config['samples'][sample_id]['mutations_file']
        
        file_name = os.path.join(config['working_dir'], file_name)
        
        all_data[sample_id] = _load_sample_allelic_prevalences(file_name, mutations_file_format)       
    
    sample_ids = all_data.keys()
    
    common_mutations = set.intersection(*[set(x.keys()) for x in all_data.values()])
    
    data = OrderedDict()
    
    for mutation_id in common_mutations:
        data[mutation_id] = OrderedDict()
        
        for sample_id in sample_ids:
            data[mutation_id][sample_id] = all_data[sample_id][mutation_id]

    return data
          
def _load_sample_allelic_prevalences(file_name, file_format):
    '''
    Load data from PyClone formatted input file.
    '''
    data = OrderedDict()
    
    if file_format == 'yaml':
        fh = open(file_name)
            
        config = yaml.load(fh)
        
        fh.close()
    
        for mutation_dict in config['mutations']:
            mutation = load_mutation_from_dict(mutation_dict)
    
            data[mutation.id] = mutation.var_counts / (mutation.ref_counts + mutation.var_counts)
    
    else:
        fh = open(file_name)
        
        reader = csv.DictReader(fh, delimiter='\t')
        
        for row in reader:
            a = int(row['ref_counts'])
            
            b = int(row['var_counts'])
            
            d = a + b
            
            f = b / d
            
            data[row['mutation_id']] = f
        
        fh.close()
    
    return data

#=======================================================================================================================
# Load cellular prevalences for all samples
#=======================================================================================================================
def _load_cellular_prevalences(config, burnin, thin):
    all_data = OrderedDict()
    
    trace_dir = os.path.join(config['working_dir'], config['trace_dir'])
    
    sample_ids = config['samples'].keys()
    
    for sample_id in sample_ids:
        file_name = os.path.join(trace_dir, '{0}.cellular_frequencies.tsv.bz2'.format(sample_id))
        
        mean_data, std_data = _load_sample_cellular_prevalences(file_name, burnin, thin)
        
        all_data[sample_id] = mean_data
        
        all_data['{0}_std'.format(sample_id)] = std_data       

    common_mutations = set.intersection(*[set(all_data[x].keys()) for x in sample_ids])
    
    data = OrderedDict()
    
    for mutation_id in sorted(common_mutations):
        data[mutation_id] = OrderedDict()
        
        for sample_id in sample_ids:
            mean_key = sample_id
            
            std_key = '{0}_std'.format(sample_id)
            
            data[mutation_id][mean_key] = all_data[mean_key][mutation_id]
            
            data[mutation_id][std_key] = all_data[std_key][mutation_id]

    return data 

def _load_sample_cellular_prevalences(file_name, burnin, thin):
    mean_data = OrderedDict()
    
    std_data = OrderedDict()
    
    trace = load_cellular_frequencies_trace(file_name, burnin, thin)
    
    for mutation_id in trace:
        mutation_trace = pd.Series(trace[mutation_id])

        mean_data[mutation_id] = mutation_trace.mean()
        
        std_data[mutation_id] = mutation_trace.std()
    
    return mean_data, std_data

def _load_plot_data(config_file, data, get_error_data=False):
    config = _load_yaml_config(config_file)
    
    sample_ids = config['samples'].keys()

    plot_cols = sample_ids + ['cluster_id', ]
    
    plot_data = data[plot_cols]
    
    if get_error_data:
        error_cols = ['{0}_std'.format(x) for x in sample_ids] + ['cluster_id', ]
    
        error_data = data[error_cols]
    
    else:
        error_data = None
    
    return plot_data, error_data