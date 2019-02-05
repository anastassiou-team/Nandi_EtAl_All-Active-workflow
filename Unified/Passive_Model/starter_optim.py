#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Feb  1 15:50:49 2018

@author: anin
"""

import os
import allensdk
from allensdk.core.cell_types_cache import CellTypesCache
import allensdk.core.swc as swc
import numpy as np
import errno
import json
import collections
import glob


import get_features

junction_potential = -14
temperature = 34
acceptable_stimtypes = [
    'Long Square'
    ]


distinct_id_map = {
    'Long Square': 'LongDC',
    'Ramp': 'Ramp',
    'Square - 2s Suprathreshold': 'LongDCSupra',
    'Ramp to Rheobase': 'RampRheo'
}

optframework_stimtype_map = {
    'Long Square': 'SquarePulse',
    'Ramp': 'RampPulse',
    'Square - 2s Suprathreshold': 'SquarePulse',
    'Ramp to Rheobase': 'RampPulse'
}


with open('passive_param_bounds.json','r') as bound_file:
        passive_params_dict = json.load(bound_file)
        
passive_params = passive_params_dict.keys()

section_map = {'soma':'somatic',
                 'apic':'apical',
                 'dend':'basal',
                 'axon':'axonal',
                 'all' : 'all'}


parent_dir = os.path.abspath(os.path.join('.', os.pardir))
path_to_cell_metadata = glob.glob(parent_dir+'/*.json')[0] 
with open(path_to_cell_metadata,'r') as metadata:
        cell_metadata = json.load(metadata)   


def calc_stimparams(time, stimulus_trace,trace_name):
    """Calculate stimuls start, stop and amplitude from trace"""

    nonzero_indices = np.where(stimulus_trace != 0)[0]

    # make sure if the stimulus is ok if there was no input
    
    # if the stimulus is zero
    if not nonzero_indices.any():   # if the list is empty
        # arbitrary values for the no-stimulus response
        stim_start = time[20000]    # after 100ms
        stim_stop = time[-1]        # until the end
        stim_amp_start = 0
        stim_amp_end = 0
        hold_curr = 0
    else:
        # if the stimulus is not zero
        stim_start = time[nonzero_indices[0]]
        stim_stop = time[nonzero_indices[-1]]
        if 'DC' in trace_name:
            hold_curr = np.mean(stimulus_trace[nonzero_indices[-1]+1000:\
                                               nonzero_indices[-1] + 20000])*1e12
        stim_amp_start = stimulus_trace[nonzero_indices[0]] * 1e12 
        stim_amp_end = stimulus_trace[nonzero_indices[-1]] * 1e12
        
    tot_duration = time[-1]    
    return stim_start, stim_stop, stim_amp_start, stim_amp_end, tot_duration, hold_curr


def calc_stimparams_nonstandard(time, stimulus_trace,trace_name):
    """Calculate stimuls start, stop and amplitude from trace for nonstandard nwb"""

    # if the stimulus is not empty
    # find the max/min of the noisy signal
    gradient_thresh = 10  # arbitrary
    gradient_f = np.gradient(stimulus_trace)*1e12
    gradient_f[abs(gradient_f) <= gradient_thresh] = 0
    
    nonzero_indices = np.where(gradient_f != 0)[0]

    if not nonzero_indices.any():
        
        stim_start = time[20000]    # after 100ms (arbitrary)
        stim_stop = time[40000]     # after 200ms (arbitrary)
        stim_amp_start = 0.0
        stim_amp_end = 0.0
        hold_curr =  np.mean(stimulus_trace[-20000:])*1e12
   
    else:
        
        signal_max = max(gradient_f)
        signal_min = min(gradient_f)
    
        # find the max/min of the gradient
        first_ind = np.where(gradient_f == signal_max)[0][0]
        second_ind = np.where(gradient_f == signal_min)[0][0]
    
        # check for the first and second indexes
        if first_ind > second_ind:
            start_ind = second_ind
            end_ind = first_ind
        elif first_ind < second_ind:
            start_ind = first_ind
            end_ind = second_ind
    
        stim_start = time[start_ind]
        stim_stop = time[end_ind]
    
        # check for the middle part of the signal
    
        # approximate the amp, it is the mean between the start and end
        if 'DC' in trace_name:
            hold_curr = np.mean(stimulus_trace[end_ind+1000:end_ind + 20000])*1e12
        else:
            hold_curr = 0
        stim_amp = np.mean(stimulus_trace[start_ind:end_ind] ) * 1e12
        stim_amp_start=stim_amp
        stim_amp_end=stim_amp
    tot_duration = time[-1]

    return stim_start, stim_stop, stim_amp_start, stim_amp_end, tot_duration, hold_curr

def write_stimmap_csv(stim_map, output_dir, stim_sweep_map):
    """Write StimMap.csv"""

    stim_reps_sweep_map = {}

    stimmapreps_csv_content = "DistinctID, StimType, HoldingCurrent, "\
        "Amplitude_Start, Amplitude_End, Stim_Start, Stim_End, Duration, DataPath\n"

    reps = collections.defaultdict(lambda: collections.defaultdict(list))
    for stim_type in stim_map:
        for trace_params in stim_map[stim_type]:


            amplitude = str(trace_params[3])+'&'+ str(trace_params[6])
            reps[stim_type][amplitude].append(trace_params)

    for stim_type in reps:
        for amplitude in reps[stim_type]:

            cumul_params = reps[stim_type][amplitude][0]

            trace_name = cumul_params[0]

            cumul_params[2] = np.mean(
                [rep_params[2] for rep_params in reps
                 [stim_type][amplitude]])

            cumul_params[8] = "|".join(
                rep_params[8] for rep_params in reps[stim_type][amplitude])

            rep_names = [rep_params[0]
                         for rep_params in reps[stim_type][amplitude]]
            rep_sweeps = [stim_sweep_map[rep_name] for rep_name in rep_names]
            stim_reps_sweep_map[trace_name] = rep_sweeps

            tstart_set = set(['.1f' % rep_params[5]
                              for rep_params in reps[stim_type][amplitude]])
            if len(tstart_set) != 1:
                raise Exception(
                    "Stim type %s Amplitude %s don't have equal start "
                    "times: %s" %
                    (stim_type, amplitude.split('&')[0], str(tstart_set)))

            tstop_set = set(['.1f' % rep_params[6]
                             for rep_params in reps[stim_type][amplitude]])
            if len(tstop_set) != 1:
                raise Exception(
                    "Stim type %s Amplitude %s don't have equal stop "
                    "times: %s" %
                    (stim_type, amplitude.split('&')[0], str(tstop_set)))

            stimmapreps_csv_content += ",".join([str(x) for x in cumul_params])
            stimmapreps_csv_content += '\n'

    stimmapreps_csv_filename = os.path.join(output_dir, 'StimMapReps.csv')

    with open(stimmapreps_csv_filename, 'w') as stimmapreps_csv_file:
        stimmapreps_csv_file.write(stimmapreps_csv_content)

    return stim_reps_sweep_map

def write_provenance(
        output_dir,
        nwb_filename,
        stim_sweep_map,
        stim_reps_sweep_map):
    """Writing provenance file"""

    provenance_filename = os.path.join(output_dir, 'provenance.json')

    nwb_md5hash = calculate_md5hash(nwb_filename)

    provenance = {
        'nwb_filename': os.path.abspath(nwb_filename),
        'nwb_md5hash': nwb_md5hash,
        'temperature': temperature,
        'junction_potential': junction_potential,
        'stim_sweep_map': stim_sweep_map,
        'stim_reps_sweep_map': stim_reps_sweep_map}

    with open(provenance_filename, 'w') as provenance_file:
        json.dump(
            provenance,
            provenance_file,
            sort_keys=True,
            indent=4,
            separators=(
                ',',
                ': '))


def calculate_md5hash(filename):
    """Calculate the md5hash of a file"""

    import hashlib
    with open(filename, 'rb') as file_h:
        md5hash = hashlib.md5(file_h.read()).hexdigest()

    return md5hash




def get_cell_data(nwb_path, non_standard_nwb = False):

    nwb_file = allensdk.core.nwb_data_set.NwbDataSet(nwb_path)
    
    stim_map = collections.defaultdict(list)
    stim_sweep_map = {}
    output_dir = os.getcwd() +'/preprocessed'
    
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise             
                
    for sweep_number in nwb_file.get_sweep_numbers():
        sweep_data = nwb_file.get_sweep_metadata(sweep_number)
        stim_type = sweep_data['aibs_stimulus_name']

        if stim_type in acceptable_stimtypes:
            sweep = nwb_file.get_sweep(sweep_number)

            start_idx, stop_idx = sweep['index_range']

            stimulus_trace = sweep['stimulus'][start_idx:stop_idx]
            response_trace = sweep['response'][start_idx:stop_idx]

            sampling_rate = sweep['sampling_rate']

            time = np.arange(0, len(stimulus_trace)) / sampling_rate
            trace_name = '%s_%d' % (
            distinct_id_map[stim_type], sweep_number)
            
            
            if non_standard_nwb:
                calc_stimparams_func = calc_stimparams_nonstandard
            else:
                calc_stimparams_func = calc_stimparams
            
            stim_start, stim_stop, stim_amp_start, stim_amp_end, tot_duration,hold_curr = calc_stimparams_func(
                time, stimulus_trace,trace_name)
         

            response_trace_short_filename = '%s.%s' % (trace_name, 'txt')

            response_trace_filename = os.path.join(
                output_dir, response_trace_short_filename)
            

            
            time = time * 1000.0
            response_trace = response_trace * 1000 + junction_potential
            time_end = time[-1]
            response_end = response_trace[-1]
            
            # downsampling
            time = time[::5]
            response_trace = response_trace[::5]
            if time_end != time[-1]:
                time = np.append(time,time_end)
                response_trace = np.append(response_trace,response_end)
                
            with open(response_trace_filename, 'w') as response_trace_file:
                np.savetxt(response_trace_file,
                              np.transpose([time, response_trace]))
            
            # Ignore holding current
            holding_current = hold_curr  # sweep['bias_current']

            stim_map[distinct_id_map[stim_type]].append([
                trace_name,
                optframework_stimtype_map[stim_type],
                holding_current/1e12,
                stim_amp_start /1e12,
                stim_amp_end/1e12,
                stim_start * 1e3,
                stim_stop * 1e3,
                tot_duration * 1e3,
                response_trace_short_filename])

            stim_sweep_map[trace_name] = sweep_number
            
    print 'Writing stimmap.csv ...',

    stim_reps_sweep_map = write_stimmap_csv(stim_map, output_dir, stim_sweep_map)
    
    write_provenance(
        output_dir,
        nwb_path,
        stim_sweep_map,
        stim_reps_sweep_map)

    
    
    return output_dir

def get_filepath_for_exten(exten, topdir = '.'):
    dir_list = list()
    
    def step(ext, dirname, names):
        ext = ext.lower()
        for name in names:
            if name.lower().endswith(ext):
                dir_list.append(os.path.join(dirname, name)) 
                
    os.path.walk(topdir, step, exten)
    return dir_list


def get_ephys_data(exten = '.nwb'):
    dir_list = get_filepath_for_exten(exten)
    return dir_list

def get_cell_morphology(exten = '.swc'):
    dir_list = get_filepath_for_exten(exten)
    morph_path = [str_path for str_path in dir_list if 'cell_types' in str_path][0]
    return morph_path


def get_cell_model(exten = '.json'):
    dir_list = get_filepath_for_exten(exten)
    param_path = [str_path for str_path in dir_list if 'fit_parameters' in str_path]
    if param_path:
        param_path = param_path[0]
    else:
       param_path = None 
    return param_path  

def get_params(param_path, no_apical = False, v_init = -80):
    model_params = list()
    if param_path:
        with open(param_path) as json_file:  
            data = json.load(json_file)
        for key, values in data.iteritems():            
            if key == 'genome':
                for j in range(len(values)):
                    if data[key][j]['name'] in passive_params:
                        
                        if no_apical and data[key][j]['section'] == 'apic': # if no apical dendrite in morphology
                            continue
                        if data[key][j]['section'] in passive_params_dict[data[key][j]['name']]['section']:
                            section = section_map[data[key][j]['section']]
                            iter_dict = {'param_name':data[key][j]['name']}
                            iter_dict['dist_type'] = 'uniform'
                            iter_dict['sectionlist'] = section
                            iter_dict['value'] = float(data[key][j]['value'])
                            iter_dict['type'] = 'section'
                            model_params.append(iter_dict)
                            
                        elif data[key][j]['section'] == 'soma':
                            section = section_map[data[key][j]['section']]
                            iter_dict = {'param_name':data[key][j]['name']}
                            iter_dict['dist_type'] = 'uniform'
                            iter_dict['sectionlist'] = 'all'
                            iter_dict['value'] = float(data[key][j]['value'])
                            iter_dict['type'] = 'section'
                            model_params.append(iter_dict)
                            
    else:
        
        for passive_param,passive_dict in passive_params_dict.items():
            for sect in passive_dict['section']:
                 if no_apical and sect == 'apic':
                     continue
                 iter_dict = {'param_name': passive_param}
                 iter_dict['sectionlist'] = section_map[sect]
                 iter_dict['type'] = 'section'
                 iter_dict['dist_type'] = 'uniform'
                 model_params.append(iter_dict)
            
    model_params.append({"param_name": "celsius","type": "global","value": 34})     
    model_params.append({"param_name": "v_init","type": "global","value": v_init})
    
    return model_params

def write_params_json(model_params,param_path,cell_id):
    release_params = dict()

    for param_dict in model_params:
        param_name = param_dict['param_name']
        if 'sectionlist' in param_dict.keys():
            param_sect = param_dict['sectionlist']
        inverted_sect_key = next(key for key,val in section_map.items() if val == param_sect)

        if param_name in passive_params:
            lb,ub = passive_params_dict[param_name]['bounds'][inverted_sect_key]
            bound = [lb, ub]
            param_dict['bounds'] =  bound
            if param_path:
                release_params[param_name + '.' + param_dict['sectionlist']] = param_dict['value']
                del param_dict['value']
            
    param_write_path = 'config/'+ cell_id + '/parameters.json'
    
    if not os.path.exists(os.path.dirname(param_write_path)):
        try:
            os.makedirs(os.path.dirname(param_write_path))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
                
    with open(param_write_path, 'w') as outfile:
        json.dump(model_params, outfile,indent=4)    
    return model_params, param_write_path, release_params

def write_mechanisms_json(param_path,cell_id):
    model_mechs = {'all':['pas']}

    
    mechanism_write_path = 'config/'+ cell_id + '/mechanism.json'
    if not os.path.exists(os.path.dirname(mechanism_write_path)):
        try:
            os.makedirs(os.path.dirname(mechanism_write_path))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    with open(mechanism_write_path, 'w') as outfile:
        json.dump(model_mechs, outfile,indent=4)
        
    return model_mechs, mechanism_write_path


def Main(): 
    cell_id = cell_metadata['Cell_id']
    dir_list = get_ephys_data()
    nwb_path = [str_path for str_path in dir_list if 'cell_types' in str_path][0]
    non_standard_nwb = cell_metadata['Area'] == 'DG'
    preprocessed_dir = get_cell_data(nwb_path,non_standard_nwb = non_standard_nwb)
    morph_path = get_cell_morphology()
    
    # check if there is an apical dendrite
    morphology = swc.read_swc(morph_path)
    no_apical = True
    for n in morphology.compartment_list:
        if n['type']==4 :
            no_apical = False
            break
    
    param_path = get_cell_model()
    cell_map = {}
    cell_name = cell_id
    cell_map[cell_name] = \
        {
            'ephys': preprocessed_dir,
            'morphology': morph_path,
            'feature_set_map':'feature_set.json',
            'v_init' : -80
        }
        
    
    features_write_path,protocols_write_path,all_protocols_write_path = get_features.run(cell_map, 
            force_feature_extraction=True)
    
    
    model_params= get_params(param_path,no_apical)  
    model_params, param_write_path,\
                    release_params = write_params_json(model_params,param_path,cell_id) 
    
    model_mechs, mechanism_write_path = write_mechanisms_json(param_path,cell_id)
    
    path_dict =  dict()
    path_dict['morphology'] = morph_path
    path_dict['parameters'] = param_write_path
    path_dict['mechanism'] = mechanism_write_path
    path_dict['features'] = features_write_path
    path_dict['protocols'] = protocols_write_path
    path_dict['all_protocols'] = all_protocols_write_path
    path_dict['release_params'] = release_params
    path_dict['fit_json'] = param_path
    
    with open('config_file.json', 'w') as outfile:
        json.dump(path_dict, outfile,indent=4)
    
    
if __name__ == '__main__': 
    Main()