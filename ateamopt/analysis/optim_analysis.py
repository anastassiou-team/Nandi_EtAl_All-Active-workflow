
import os
import numpy as np
import glob
import logging
import bluepyopt.ephys as ephys
from collections import defaultdict
from collections import OrderedDict
import pandas as pd
from ateamopt.utils import utility
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import math
import efel
from .analysis_module import get_spike_shape

logger = logging.getLogger(__name__)

class Optim_Analyzer(object):

    def __init__(self,opt_obj=None,cp_dir=None):
        self._opt = opt_obj
        self.cp_dir = cp_dir
        if self.cp_dir:
            self._cp_path = self.get_best_cp_seed() # the seed file with minimum error
        else:
            self._cp_path = None

    def get_best_cp_seed(self):
        checkpoint_dir  = os.path.join(self.cp_dir,'seed*.pkl')
        file_list = glob.glob(checkpoint_dir)

        cp_min = float('inf')
        for filename in file_list:
            cp = utility.load_pickle(filename)
            cp_log = cp['logbook']
            cp_log_min =  np.min(np.array(cp_log.select('min')))
            if cp_log_min < cp_min:
                cp_min = cp_log_min
                cp_best = filename
        try:
            logger.debug('Best checkpoint file is %s with min. objective %s'\
                         %(cp_best.split('/')[-1],cp_min))
        except:
            logger.debug('No checkpoint file available at specified path')

        return cp_best


    def get_best_model(self, hof_idx = 0):
        checkpoint = utility.load_pickle(self._cp_path)
        best_model = [checkpoint['halloffame'][hof_idx]] # least training error
        return best_model


    def get_all_models(self):
        checkpoint_dir  = os.path.join(self.cp_dir,'seed*.pkl')
        cp_list = glob.glob(checkpoint_dir)

        hof_params = []
        seed_indices = []
        for i,cp_file in enumerate(cp_list):
            hof_i = utility.load_pickle(cp_file)['halloffame']
            hof_params.extend(hof_i)
            seed = [cp_file.split('/')[1].split('.')[0]]*len(hof_i)
            seed_indices.extend(seed)

        return hof_params, seed_indices


    def get_model_responses(self,hof_params,
                          hof_responses_filename='analysis_params/hof_response_all.pkl'):
        utility.create_filepath(hof_responses_filename)

        # Calculate responses for the hall-of-fame parameters
        if not os.path.exists(hof_responses_filename):
            logger.debug('Calculating Hall of Fame Responses')
            hof_response_list = list(self._opt.toolbox.map(self._opt.toolbox.save_sim_response,
                                                       hof_params))
            utility.save_pickle(hof_responses_filename,hof_response_list)
        else:
            logger.debug('Retrieving Hall of Fame Responses')
            hof_response_list = utility.load_pickle(hof_responses_filename)

        return hof_response_list


    def get_response_scores(self,response_list):
        logger.debug('Calculating Objectives for Responses')
        opt = self._opt
        obj_list = list(opt.toolbox.map(opt.toolbox.evaluate_response,response_list))
        return obj_list

    @staticmethod
    def organize_models(param_list, score_list_train):
        param_list_arranged = [x for _,x in sorted(zip(score_list_train,param_list))]
        return param_list_arranged


    @staticmethod
    def save_best_response(response, response_filename):
        utility.create_filepath(response_filename)
        utility.save_pickle(response_filename, response)


    def save_hof_output_params(self, hof_params, hof_params_filename,
                               score_list_train = None):
        utility.create_filepath(hof_params_filename)
        if score_list_train:
            hof_params_arranged = self.organize_models(hof_params,score_list_train)
        else:
            hof_params_arranged= hof_params
        utility.save_pickle(hof_params_filename, hof_params_arranged)
        return hof_params_arranged

    def save_GA_evolultion_info(self,GA_evol_path):

        checkpoint = utility.load_pickle(self._cp_path)

        log = checkpoint['logbook']
        gen_numbers = log.select('gen')
        mean = np.array(log.select('avg'))
        std = np.array(log.select('std'))
        minimum = np.array(log.select('min'))

        logger.debug('Saving the plot_GA_evolution parameters')
        GA_evolution_params = {'gen_numbers': gen_numbers,
                                     'mean' : mean,
                                     'std' : std,
                                     'minimum' : minimum}
        utility.create_filepath(GA_evol_path)
        utility.save_pickle(GA_evol_path,GA_evolution_params)


    def get_release_responses(self,opt_release,response_release_filename):

        if response_release_filename and os.path.exists(response_release_filename):
            responses_release = utility.load_pickle(response_release_filename)
            logger.debug('Retrieving Released Responses')
        else:

            utility.create_filepath(response_release_filename)
            fitness_protocols = self._opt.evaluator.fitness_protocols
            responses_release = {}
            release_params_original = {} # Parameters already optimized for released case

            if opt_release:
                logger.debug('Calculating Released Responses')
                nrn = ephys.simulators.NrnSimulator()
                for protocol in fitness_protocols.values():
                    response_release = protocol.run(
                            cell_model=opt_release.evaluator.cell_model,
                            param_values=release_params_original,
                            sim=nrn)
                    responses_release.update(response_release)

            utility.save_pickle(response_release_filename, responses_release)


    def create_bpopt_param_template(self,param_list):
        opt = self._opt
        bpopt_section_map_inv = utility.bpopt_section_map_inv

        optimized_param_dict = {key:param_list[i] for i,key in \
                            enumerate(opt.evaluator.param_names)}

        param_dict = {key.split('.')[0]+'.'+
                     bpopt_section_map_inv[key.split('.')[1]] : optimized_param_dict[key]
                                            for key in optimized_param_dict.keys()}

        return param_dict

    def create_aibs_param_template(self,param_list,
                                   expand_params = False,
                                   opt_config_file='config_file.json'):
        opt_config = utility.load_json(opt_config_file)
        bpopt_param_path = opt_config['parameters']
        morph_path = opt_config['morphology']

        # Check for apical dendrite
        no_apical = utility.check_swc_for_apical(morph_path)

        bpopt_sim_params = utility.load_json(bpopt_param_path)
        bpopt_section_map = utility.bpopt_section_map
        bpopt_section_map_inv = utility.bpopt_section_map_inv


        param_dict = self.create_bpopt_param_template(param_list)

        aibs_format_params = defaultdict(list)
        aibs_format_params['passive'].append({'ra' : param_dict['Ra.all']})
        aibs_format_params['fitting'].append({
                'junction_potential' : -14.0,
                 'sweeps' : []
                 })

        ena_sectionlist = [bpopt_section_map_inv[x['sectionlist']] for x in bpopt_sim_params \
                           if x['param_name'] == 'ena']
        ek_sectionlist = [bpopt_section_map_inv[x['sectionlist']] for x in bpopt_sim_params \
                           if x['param_name'] == 'ek']

        sect_reject_list = ['all']
        if no_apical:sect_reject_list.append('apic')
        temp_sect_map_inv = [sect for sect in bpopt_section_map_inv \
                             if sect not in sect_reject_list]

        erev_list = []
        for sect_ in temp_sect_map_inv:
            temp_dict = {}
            if sect_ in ena_sectionlist:
                temp_dict['ena'] = utility.rev_potential['ena']

            if sect_ in ek_sectionlist:
                temp_dict['ek'] = utility.rev_potential['ek']

            if bool(temp_dict):
                temp_dict['section'] = sect_
                erev_list.append(temp_dict)


        aibs_format_params['conditions'].append({'celsius' : next(item['value'] \
                              for item in bpopt_sim_params if \
                              item["param_name"] == "celsius"),
                          "erev": erev_list,
                          "v_init": next(item['value'] for item in bpopt_sim_params if \
                                        item["param_name"] == "v_init")
                          })

        if expand_params:
            # If section == 'all' distribute to all section names

            param_all_entries = {}
            param_del_entries = []
            sect_reject_list_bpopt = [bpopt_section_map[sect_] for sect_ in sect_reject_list]
            temp_sect_map = [sect for sect in bpopt_section_map \
                             if sect not in sect_reject_list_bpopt]

            for param,val in param_dict.items():
                param_name,sect = param.split('.')
                if sect == 'all':
                    for sec_ in temp_sect_map:
                        param_all_entries.update({'%s.%s'%(param_name,sec_):\
                                                  val})
                    param_del_entries.append(param)

            # delete the all entries and repopulate with the four section names
            param_dict = utility.remove_entries_dict(param_dict,param_del_entries)
            param_dict.update(param_all_entries)


        for param,val in param_dict.items():
            param_name,sect = param.split('.')
            param_match = list(filter(lambda x:x['param_name'] == param_name,
                           bpopt_sim_params))[0]
            if 'mechanism' in param_match:
                mech = param_match['mech']
            else:
                mech = ''

            aibs_format_params['genome'].append(
                    {
                      'section' : sect,
                      'name'    : param_name,
                      'value'   : str(val),
                      'mechanism': mech
                    })

        return aibs_format_params

    def plot_grid_Response(self,response_filename,
                      response_release_filename,
                      stim_file,
                      pdf_pages,
                      save_model_response = False,
                      model_response_dir = 'model_response/',
                      ephys_dir= 'preprocessed/',
                      opt_config_file='config_file.json'):

        stim_df = pd.read_csv(stim_file, sep='\s*,\s*',
                               header=0, encoding='ascii', engine='python')

        opt_config = utility.load_json(opt_config_file)
        train_protocol_path = opt_config['protocols']
        released_model = opt_config['released_model']

        train_protocols = utility.load_json(train_protocol_path)

        opt = self._opt # Optimizer object

        response = utility.load_pickle(response_filename)[0] # response with minimum training error
        responses_release = utility.load_pickle(response_release_filename)
        logger.debug('Retrieving Optimized and Released Responses')


        # Saving model response for hof[0]
        if save_model_response:
            utility.create_dirpath(model_response_dir)

        plt.style.use('ggplot')
        all_plots = 0

        protocol_names_original = stim_df['DataPath'].tolist()
        amp_start_original = stim_df['Stim_Start'].tolist()
        amp_end_original = stim_df['Stim_End'].tolist()

        protocol_names = sorted(protocol_names_original)
        idx = np.argsort(protocol_names_original)
        amp_start_list = [amp_start_original[i] for i in idx]
        amp_end_list = [amp_end_original[i] for i in idx]

        for i, trace_rep in enumerate(protocol_names):
            rep_id = trace_rep.split('|')[0]
            if rep_id.split('.')[0] in opt.evaluator.fitness_protocols.keys():
                all_plots += len(trace_rep.split('|'))
        n_col = 3; n_row = 5
        fig_per_page = n_col * n_row
        fig_pages =  int(math.ceil(all_plots/float(fig_per_page)))
        fig_mat = list()
        ax_mat = list()
        for page_i in range(fig_pages):

            fig,ax = plt.subplots(n_row,n_col, figsize=(10,10),squeeze = False)

            if page_i == fig_pages-1:
                remain_plots = all_plots - n_row*n_col*(fig_pages-1)
                fig_empty_index_train = range(remain_plots,n_row*n_col)


                if len(fig_empty_index_train) != 0:
                    for ind in fig_empty_index_train:
                        ax[ind//n_col,ind%n_col].axis('off')

            fig_mat.append(fig)
            ax_mat.append(ax)


        index = 0
        index_plot = 0
        fig_index = 0

        for ix,trace_rep in enumerate(protocol_names):
            rep_id = trace_rep.split('|')[0]
            if rep_id.split('.')[0] in train_protocols.keys():
                state = ' (Train)'
            else:
                state = ' (Test)'
            name_loc = rep_id.split('.')[0] +'.soma.v'
            if rep_id.split('.')[0] in opt.evaluator.fitness_protocols.keys():

                for name in trace_rep.split('|'):
                    ax_comp = ax_mat[fig_index]
                    fig_comp = fig_mat[fig_index]
                    response_time = response[name_loc]['time']
                    response_voltage = response[name_loc]['voltage']

                    color = 'blue'
                    l1, = ax_comp[index//n_col,index%n_col].plot(response_time,
                            response_voltage,
                            color=color,
                            linewidth=1,
                            label= 'Model',
                            alpha = 0.8)

                    if save_model_response:
                        model_response_filename = model_response_dir + '%s'%name
                        with open(model_response_filename, 'w') as handle:
                            np.savetxt(handle,
                                          np.transpose([response_time.values,
                                                        response_voltage.values]))

                    FileName = ephys_dir + name
                    data = np.loadtxt(FileName)
                    if any(data[:,1]):
                        exp_time  = data[:,0]
                        exp_voltage = data[:,1]

                    else: # stolen triblip protocol
                        exp_time,exp_voltage = [],[]

                    l3, = ax_comp[index//n_col,index%n_col].plot(exp_time,
                                exp_voltage,
                                color='black',
                                linewidth=1,
                                label = 'Experiment',
                                alpha = 0.8)
                    if released_model:
                        responses_release_time = responses_release[name_loc]['time']
                        responses_release_voltage = responses_release[name_loc]['voltage']
                        l4,=ax_comp[index//n_col,index%n_col].plot(responses_release_time,
                                responses_release_voltage,
                                color='r',
                                linewidth=.1,
                                label = 'Released',
                                alpha = 0.4)



                    if index//n_col == n_row-1:
                        ax_comp[index//n_col,index%n_col].set_xlabel('Time (ms)')
                    if index%n_col == 0:
                        ax_comp[index//n_col,index%n_col].set_ylabel('Voltage (mV)')
                    ax_comp[index//n_col,index%n_col].set_title(name.split('.')[0] + state, fontsize=8)

                    if 'LongDC' in name:
                        ax_comp[index//n_col,index%n_col].set_xlim([amp_start_list[ix]-200,\
                                                                  amp_end_list[ix]+200])

                    logger.debug('Plotting response comparisons for %s \n'%name.split('.')[0])
                    index += 1
                    index_plot +=1
                    if index%fig_per_page == 0 or index_plot == all_plots:
                        fig_comp.suptitle('Response Comparisons',fontsize=16)
                        if released_model:
                            handles = [l1, l3, l4]
                            ncol = 3
                        else:
                             handles = [l1, l3]
                             ncol = 2
                        labels = [h.get_label() for h in handles]
                        fig_comp.legend(handles = handles, labels=labels, loc = 'lower center', ncol=ncol)
                        fig_comp.tight_layout(rect=[0, 0.03, 1, 0.95])
                        pdf_pages.savefig(fig_comp)
                        plt.close(fig_comp)
                        index = 0
                        fig_index += 1


        return pdf_pages

    def plot_feature_comp(self, response_filename,
                     response_release_filename,
                     pdf_pages,
                     opt_config_file = 'config_file.json'):

        # objectives
        opt = self._opt # Optimizer object
        opt_response = utility.load_pickle(response_filename)[0]
        responses_release =  utility.load_pickle(response_release_filename)

        opt_config = utility.load_json(opt_config_file)
        train_protocol_path = opt_config['protocols']
        released_model = opt_config['released_model']
        train_protocols = utility.load_json(train_protocol_path)

        logger.debug('Calculating Objectives for Optimized and Released Responses')

        objectives = opt.evaluator.fitness_calculator.calculate_scores(opt_response)
        objectives_release = opt.evaluator.fitness_calculator.calculate_scores(responses_release)

        objectives = OrderedDict(sorted(objectives.items()))
        objectives_release = OrderedDict(sorted(objectives_release.items()))

        feature_split_names = [name.split('.',1)[-1] for name in objectives.keys()]
        features = np.unique(np.asarray(feature_split_names))

        bar_width = 0.35
        opacity = 0.4

        plt.style.use('ggplot')
        for i, feature in enumerate(features):
            fig, ax = plt.subplots(1, figsize=(8,8))
            iter_dict = defaultdict(list)
            iter_dict_release = defaultdict(list)
            for key in objectives.keys():
                if key.split('.',1)[-1] == feature:
                    amp = train_protocols[key.split('.')[0]]['stimuli'][0]['amp']
                    amp_reduced = round(amp,3)
                    iter_dict[str(amp_reduced)].append(objectives[key])
                    iter_dict_release[str(amp_reduced)].append(objectives_release[key])
            index = np.arange(len(iter_dict.keys()))
            xtick_pos = index + bar_width / 2
            iter_dict ={float(key):np.mean(val) for key,val in iter_dict.items()}
            iter_dict_release ={float(key):np.mean(val) for key,val in iter_dict_release.items()}
            iter_dict = OrderedDict(sorted(iter_dict.items()))
            iter_dict_release = OrderedDict(sorted(iter_dict_release.items()))
            tick_label = iter_dict.keys()
            ax.bar(index+ bar_width,
                  list(iter_dict.values()),
                  bar_width,
                  align='center',
                  color='b',
                  alpha=opacity,
                  label='Optimized')
            if released_model:
                ax.bar(index,
                      list(iter_dict_release.values()),
                      bar_width,
                      align='center',
                      color='r',
                      alpha=opacity,
                      label='Released')
            ax.set_xticks(xtick_pos)
            ax.set_xticklabels(tick_label, fontsize= 8)
            plt.xticks(rotation=90)
            for tick in ax.yaxis.get_major_ticks():
                tick.label.set_fontsize(8)
            ax.set_ylabel('Objective value (# std)',fontsize= 12)
            ax.set_xlabel('Stimulus Amplitude (nA)',fontsize= 12)
            ax.legend(prop={'size': 12},loc ='best')
            if 'soma' in feature:
                feature_title = feature.split('.')[1]
            else:
                feature_title = feature.split('.')[1] + ' at ' + feature.split('.')[0]
            ax.set_title(feature_title, fontsize= 14)
            fig.tight_layout(rect=[0.05, 0.05, .95, 0.95])
            pdf_pages.savefig(fig)
            plt.close(fig)
            logger.debug('Plotting comparisons for %s \n'%feature)

        return pdf_pages

    def plot_param_diversity(self,hof_params_filename,
                             pdf_pages,
                             opt_config_file = 'config_file.json'):

        opt = self._opt
        best_individual = self.get_best_model()
        hof_list = utility.load_pickle(hof_params_filename)

        opt_config = utility.load_json(opt_config_file)
        release_params_bpopt = opt_config['release_params_bpopt']
        param_names = opt.evaluator.param_names
        param_values = opt.evaluator.params
        param_names_arranged = sorted(param_names)
#        sect_names_arranged = [sect.split('.')[1] for sect in param_names_arranged]
        ix = sorted(range(len(param_names)), key=lambda k: param_names[k])
        param_values_arranged = [param_values[k] for k in ix]
        best_individual_arranged = [best_individual[0][k] for k in ix]

        all_params = param_names_arranged + list(set(release_params_bpopt.keys()) -
                                             set(param_names_arranged))
        all_params_arranged = sorted(all_params)
        release_params_arranged = sorted(release_params_bpopt.keys())
#        sect_release_names_arranged = [sect.split('.')[1] for sect in release_params_arranged]

        release_individual = list()
        for param_name in release_params_arranged:
            release_individual.append(release_params_bpopt[param_name])


        hof_list_arranged = []
        for i in range(len(hof_list)):
            arranged_hof_item = [hof_list[i][j] for j in ix]
            hof_list_arranged.append(arranged_hof_item)

        fig, ax = plt.subplots(1,figsize=(6,6))

        param_count = len(all_params_arranged)
        x = np.arange(param_count)

        x_opt = []
        x_release = []
        for i in range(param_count):
            if all_params_arranged[i] in param_names_arranged:
                x_opt.append(i)
            if all_params_arranged[i] in release_params_arranged:
                x_release.append(i)

        def add_line(ax, xpos, ypos):
            line = plt.Line2D([xpos, xpos], [ypos + .1, ypos],
                              transform=ax.transAxes, color='black')
            line.set_clip_on(False)
            ax.add_line(line)


        for k in range(len(hof_list_arranged)):
            if k == 0:
                ax.scatter(x_opt, list(map(abs,hof_list_arranged[k])), marker = 'o',
                   alpha = 0.2, s=10, color= 'green', edgecolor='black',
                   label='hall of fame')
            else:
                ax.scatter(x_opt, list(map(abs,hof_list_arranged[k])), marker = 'o',
                   alpha = 0.2, s=10, color= 'green')

        abs_optimized_individual_arranged  = list(map(abs,best_individual_arranged))
        ax.scatter(x_opt, abs_optimized_individual_arranged, marker = 'x',
                   alpha = 1, s=100, color= 'blue', edgecolor='black',
                   label='optimized')
        abs_release_individual = list(map(abs,release_individual))
        ax.scatter(x_release, abs_release_individual, marker = 'x',
                   alpha = 0.8, s=50, color= 'red', edgecolor='black',
                   label = 'released')

        tick_labels = all_params_arranged

        def plot_tick(column, y):
                    col_width = 0.3
                    x = [column - col_width,
                         column + col_width]
                    y = [y, y]
                    ax.plot(x, y, color='black',linewidth = 1)

        min_list = list()
        for i, parameter in zip(x_opt,param_values_arranged):
            min_value = abs(parameter.lower_bound)
            max_value = abs(parameter.upper_bound)
            min_list.append(min_value)
            plot_tick(i, min_value)
            plot_tick(i, max_value)

        plt.xticks(x, tick_labels, rotation=90, ha='center', fontsize = 6)
        plt.yticks(fontsize = 8)
        for xline in x:
            ax.axvline(xline, linewidth=.5, color='white',linestyle=':')
        ax.set_yscale('log')
        if min(min_list)<1e-10:
            ax.set_ylim((1e-10, 1e4))
        ax.set_xlim((-1, x[-1]+1))
        ax.set_ylabel('Parameter Values (Absolute)', fontsize = 8)
        ax.legend(prop={'size': 8}, frameon= True, shadow=True, fancybox=True)
        ax.set_title('Parameters')
        plt.tight_layout()
        pdf_pages.savefig(fig)
        plt.close(fig)

        return pdf_pages



    def plot_GA_evol(self, GA_evol_datapath,pdf_pages):

        plt.style.use('ggplot')
        GA_evolution_params = utility.load_pickle(GA_evol_datapath)
        gen_numbers = GA_evolution_params['gen_numbers']
        mean = GA_evolution_params['mean']
        std = GA_evolution_params['std']
        minimum = GA_evolution_params['minimum']

        stdminus = mean - std
        stdplus = mean + std

        fig, ax = plt.subplots(1, figsize=(8,8))
        ax.plot(gen_numbers,
                mean,
                color="white",
                linewidth=2,
                label='population average')

        ax.fill_between(gen_numbers,
            stdminus,
            stdplus,
            color='#3F5D7D',
            alpha = 0.5,
            label='population standard deviation')

        ax.plot(gen_numbers,
                minimum,
                color='red',
                linewidth=2,
                alpha = 0.8,
                label='population minimum')

        ax.legend(prop={'size': 12}, frameon= True,
                        shadow=True, fancybox=True)

        left, bottom, width, height = [0.67, 0.6, 0.2, 0.15]
        ax2 = fig.add_axes([left, bottom, width, height])

        ax2.plot(gen_numbers,
                minimum,
                linewidth=2,
                color='red',
                alpha = 0.8)

        ax2.set_facecolor('#EAECEE')
        ax2.xaxis.set_major_locator(plt.MaxNLocator(5))
        ax2.yaxis.set_major_locator(plt.MaxNLocator(4))
        ax.set_xlim((1,gen_numbers[-1]))
        ax.set_xlabel('Generation #')
        ax.set_ylabel('Sum of objectives')
        ax.set_title('Evolution of the Objective')
        pdf_pages.savefig(fig)
        plt.close(fig)

        return pdf_pages


    def save_params_aibs_format(self,save_params_filename,
                                bpopt_param_list,expand_params = False):
        utility.create_filepath(save_params_filename)
        aibs_params = self.create_aibs_param_template(bpopt_param_list,
                                              expand_params = expand_params)
        utility.save_json(save_params_filename,aibs_params)

    def save_params_bpopt_format(self,save_params_filename,
                                bpopt_param_list):
        utility.create_filepath(save_params_filename)
        bpopt_param_dict = self.create_bpopt_param_template(bpopt_param_list)
        utility.save_json(save_params_filename,bpopt_param_dict)

    def convert_aibs_param_to_dict(self,aibs_param_file,repeat_params = []):
        aibs_params = utility.load_json(aibs_param_file)
        model_param_dict = {}
        section_map = utility.bpopt_section_map

        written_repeat_params = []

        for key, values in aibs_params.items():
            if key == 'genome':
                for j in range(len(values)):
                    param_name = aibs_params[key][j]['name']
                    param_sect = section_map[aibs_params[key][j]['section']]
                    if param_name not in written_repeat_params:
                        if param_name in repeat_params:
                            param_sect = 'all'
                            written_repeat_params.append(param_name)
                        param_name_with_sect = param_name + '.' + param_sect
                        param_value = float(aibs_params[key][j]['value'])
                        model_param_dict[param_name_with_sect] = param_value

        return model_param_dict

    @staticmethod
    def prepare_spike_shape(response_filename,stim_map,
                        stim_name_select, ephys_dir= 'preprocessed/',
                        prefix_pad = 2, posfix_pad = 5,
                        res =0.05):

        response = utility.load_pickle(response_filename)[0]
        spike_features = ['peak_time']
        sweep_filenames = stim_map[stim_name_select]['stimuli'][0]['sweep_filenames']
        sweeps = []
        for sweep_filename in sweep_filenames:
            sweep_fullpath = os.path.join(
                    ephys_dir,
                    sweep_filename)
            data = np.loadtxt(sweep_fullpath)
            time = data[:, 0]
            voltage = data[:, 1]

            # Prepare sweep for eFEL
            sweep = {}
            sweep['T'] = time
            sweep['V'] = voltage
            sweep['stim_start'] = [stim_map[stim_name_select]['stimuli'][0]['delay']]
            sweep['stim_end'] = [stim_map[stim_name_select]['stimuli'][0]['stim_end']]
            sweeps.append(sweep)

        # Extract experimental spike times
        feature_results = efel.getFeatureValues(sweeps, spike_features)
        AP_shape_time = np.arange(-prefix_pad,posfix_pad, res)
        AP_shape_exp = np.zeros(AP_shape_time.size)
        AP_shape_model = np.zeros(AP_shape_time.size)

        # Experimental AP shape
        num_spikes_exp = 0
        for k,sweep_filename in enumerate(sweep_filenames):
            sweep_fullpath = os.path.join(
                ephys_dir,
                sweep_filename)

            data = np.loadtxt(sweep_fullpath)
            time = data[:, 0]
            voltage = data[:, 1]
            spike_times_exp = feature_results[k]['peak_time']
            AP_shape_exp = get_spike_shape(time,voltage,
                    spike_times_exp,AP_shape_time,
                    AP_shape_exp)
            num_spikes_exp += len(spike_times_exp)
        AP_shape_exp /= num_spikes_exp


        # Calculate model spike times
        model_sweeps = []
        model_sweep = {}
        name_loc = stim_name_select+'.soma.v'
        resp_time = response[name_loc]['time'].values
        resp_voltage = response[name_loc]['voltage'].values
        model_sweep['T'] = resp_time
        model_sweep['V'] = resp_voltage
        model_sweep['stim_start'] = [stim_map[stim_name_select]['stimuli'][0]['delay']]
        model_sweep['stim_end'] = [stim_map[stim_name_select]['stimuli'][0]['stim_end']]
        model_sweeps.append(model_sweep)
        feature_results_model = efel.getFeatureValues(model_sweeps, spike_features)

        # Model AP shape
        spike_times_model = feature_results_model[0]['peak_time']

        AP_shape_model = get_spike_shape(time,voltage,
                    spike_times_exp,AP_shape_time,
                    AP_shape_exp)

        num_spikes_model = len(spike_times_model)
        AP_shape_model /= num_spikes_model

        return AP_shape_time, AP_shape_exp, AP_shape_model

    def prepare_fI_curve(response_filename, stim_map,reject_stimtype_list,
                         ephys_dir= 'preprocessed/'):
        feature_mean_exp = defaultdict()
        stim_name_exp = defaultdict()

        somatic_features = ['Spikecount']
        spike_stim_keys_dict = {}

        for stim_name in stim_map.keys():
            stim_start = stim_map[stim_name]['stimuli'][0]['delay']
            stim_end = stim_map[stim_name]['stimuli'][0]['stim_end']
            sweeps = []
            for sweep_filename in stim_map[stim_name]['stimuli'][0]['sweep_filenames']:
                sweep_fullpath = os.path.join(
                    'preprocessed',
                    sweep_filename)

                data = np.loadtxt(sweep_fullpath)
                time = data[:,0]
                voltage = data[:,1]

                # Prepare sweep for eFEL
                sweep = {}
                sweep['T'] = time
                sweep['V'] = voltage
                sweep['stim_start'] = [stim_start]
                sweep['stim_end'] = [stim_end]

                sweeps.append(sweep)
            feature_results = efel.getFeatureValues(sweeps, somatic_features)
            for feature_name in somatic_features:
                feature_values = [np.mean(trace_dict[feature_name])
                                  for trace_dict in feature_results
                                  if trace_dict[feature_name] is not None]

            if feature_values:
                feature_mean = np.mean(feature_values)

            else:
                feature_mean = 0
            if feature_mean != 0:
                spike_stim_keys_dict[stim_name] = stim_map[stim_name]['stimuli'][0]['amp']

            stim_amp =stim_map[stim_name]['stimuli'][0]['amp']
            stim_dur = (float(stim_end) - float(stim_start))/1e3  # in seconds
            feature_mean_exp[stim_amp] = feature_mean/stim_dur
            stim_name_exp[stim_amp] = stim_name


        # Calculating the spikerate for the model
        response = utility.load_pickle(response_filename)[0]
        feature_mean_model_dict = defaultdict()
        stim_model_dict = defaultdict()

        for key,val in response.items():
            if 'soma' in key:
                if not any(stim_type_iter in key for stim_type_iter in \
                           reject_stimtype_list):
                    stim_name = key.split('.')[0]
                    if 'DB' in stim_name:
                        continue
                    resp_time = val['time'].values
                    resp_voltage = val['voltage'].values
                    stim_amp = stim_map[stim_name]['stimuli'][0]['amp']
                    trace1 = {}
                    trace1['T'] = resp_time
                    trace1['V'] = resp_voltage
                    trace1['stim_start'] = [stim_map[stim_name]['stimuli'][0]['delay']]
                    trace1['stim_end'] = [stim_map[stim_name]['stimuli'][0]['stim_end']]
                    model_traces = [trace1]
                    feature_results_model = efel.getFeatureValues(model_traces, somatic_features)
                    for feature_name in somatic_features:
                        feature_values_model = [np.mean(trace_dict[feature_name])
                                          for trace_dict in feature_results_model
                                          if trace_dict[feature_name] is not None]

                    if feature_values_model:
                        feature_mean_model = feature_values_model[0]
                    else:
                        feature_mean_model = 0

                    stim_start = stim_map[stim_name]['stimuli'][0]['delay']
                    stim_end = stim_map[stim_name]['stimuli'][0]['stim_end']
                    stim_dur = (float(stim_end) - float(stim_start))/1e3
                    feature_mean_model_dict[stim_amp] = feature_mean_model/stim_dur
                    stim_model_dict[stim_amp] = stim_name

        select_stim_keys_list = sorted(spike_stim_keys_dict, key=spike_stim_keys_dict.__getitem__)
        if len(select_stim_keys_list) > 2:
            select_stim_keys =  [select_stim_keys_list[0], select_stim_keys_list[-2]]


        return stim_name_exp,feature_mean_exp,stim_model_dict,\
                        feature_mean_model_dict,select_stim_keys

    def postprocess(self,stim_file,response_filename, pdf_pages,
                                 ephys_dir= 'preprocessed/'):
        stim_map_content = pd.read_csv(stim_file, sep='\s*,\s*',
                                   header=0, encoding='ascii', engine='python')
        reject_stimtype_list = ['LongDCSupra','Ramp', 'ShortDC',
                                'Noise','Short_Square_Triple']
        stim_map = defaultdict(dict)

        # Get the stim configuration for each stim
        for line in stim_map_content.split('\n')[1:-1]:
            if line != '':
                stim_name, stim_type, holding_current, amplitude_start, amplitude_end, \
                    stim_start, stim_end, duration, sweeps = line.split(',')
                if not any(stim_type_iter in stim_name for stim_type_iter in reject_stimtype_list):
                    iter_dict= dict()
                    iter_dict['type'] = stim_type.strip()
                    iter_dict['amp'] = 1e9 * float(amplitude_start)
                    iter_dict['delay'] = float(stim_start)
                    iter_dict['stim_end'] = float(stim_end)
                    iter_dict['sweep_filenames'] = [
                        x.strip() for x in sweeps.split('|')]

                    iter_list = [iter_dict]
                    stim_map[stim_name]['stimuli'] = iter_list

        stim_name_exp,feature_mean_exp,stim_model_dict,\
                        feature_mean_model_dict,select_stim_keys= \
                            self.prepare_fI_curve(response_filename,
                            stim_map,reject_stimtype_list,ephys_dir=ephys_dir)

        stim_exp = sorted(stim_name_exp.keys())
        mean_freq_exp = [feature_mean_exp[amp] for amp in stim_exp]

        stim_model = sorted(stim_model_dict.keys())
        mean_freq_model = [feature_mean_model_dict[amp] for amp in stim_model]
        max_freq = max([max(mean_freq_model), max(mean_freq_exp)])

        # Plot fi curve
        fig,ax= plt.subplots(1,figsize=(5,5),dpi =80)

        for key,val in stim_model_dict.items():
            if val in select_stim_keys:
                if val == select_stim_keys[0]:
                    shift = (max_freq+feature_mean_model_dict[key])/2
                else:
                    shift = -feature_mean_model_dict[key]/2
                ax.annotate(val,xy=(key,feature_mean_model_dict[key]),
                            xytext =(key,feature_mean_model_dict[key]+shift),
                            rotation=90,fontsize = 10,
                            arrowprops=dict(facecolor='red',
                            shrink=0.01,alpha =.5))
        ax.scatter(stim_exp, mean_freq_exp,color = 'black',
                   s=50, alpha = .8, label='Experiment')
        ax.plot(stim_exp, mean_freq_exp,color = 'black',lw =.1, alpha = .1)
        ax.scatter(stim_model, mean_freq_model,color = 'blue',
                   s=100,alpha = .9, marker = '*',label='Model')
        ax.plot(stim_model, mean_freq_model,color = 'blue',lw = .1, alpha = .1)
        ax.set_xlabel('Stimulation Amplitude (nA)',fontsize = 10)
        ax.set_ylabel('Spikes/sec',fontsize = 10)
        ax.legend()

        pdf_pages.savefig(fig)
        plt.close(fig)

        # Plot spike shape
        fig,ax= plt.subplots(1,len(select_stim_keys),figsize=(8,5),
                             dpi=80, sharey = True,squeeze = False)
        for kk,stim_name in enumerate(select_stim_keys):
            AP_shape_time, AP_shape_exp, AP_shape_model =\
                self.prepare_spike_shape(response_filename,stim_map,
                                         stim_name,ephys_dir=ephys_dir)
            ax[kk].plot(AP_shape_time, AP_shape_exp,lw = 2,
                          color = 'black',label = 'Experiment')
            ax[kk].plot(AP_shape_time, AP_shape_model,lw = 2,
                          color = 'blue',label = 'Model')
            ax[kk].legend(prop={'size': 10})
            ax[kk].set_title(stim_name,fontsize = 12)

        pdf_pages.savefig(fig)
        plt.close(fig)
        return pdf_pages

    def hof_statistics(self, hof_response_dir = 'analysis_params'):
        opt =self._opt
        hof_score_path = hof_response_dir + '/hof_obj.pkl'
        hof_score_list = pickle.load(open(hof_score_path,"rb"))
        feature_list = list(set(list(map(lambda x:x.split('.')[-1], hof_score_list[0].keys()))))

        hof_df_list = []
        for i, hof_score in enumerate(hof_score_list):
            obj_dict = {'index':i}
            for feature in feature_list:
                temp_list = list(map(lambda x:hof_score[x] if x.split('.')[-1] == feature else None,
                                                             hof_score.keys()))

                temp_list_filtered = list(filter(lambda x: x is not None, temp_list))
                obj_dict[feature] = np.mean(temp_list_filtered)
            hof_df_list.append(obj_dict)

        hof_df = pd.DataFrame(hof_df_list)
        hof_df_wo_index = hof_df.loc[:, hof_df.columns != 'index']


        cmap = sns.cubehelix_palette(light=1, as_cmap=True)

        fig,ax = plt.subplots(figsize = (8,6),dpi = 80)
        sns.set(style="darkgrid", font_scale=.95)

        sns.heatmap(hof_df_wo_index, cmap = cmap, ax = ax)
        plt.xticks(rotation = 45,ha="right")

        ax.set_ylabel('Hall of Fame')
        fig.tight_layout()
        pdf_pages.savefig(fig)
        plt.close(fig)


        hof_response_path = hof_response_dir+'/hof_response_all.pkl'
        hof_response_list = pickle.load(open(hof_response_path,"rb"))
        spiketimes_exp_path = 'Validation_Responses/spiketimes_exp_noise.pkl'
        if os.path.exists(spiketimes_exp_path):
            spike_times_exp_pkl = pickle.load(open(spiketimes_exp_path,"rb"))
            noise_bool = True
        else:
            noise_bool = False
        obj_train_path = hof_response_dir + '/hof_obj_train.pkl'
        obj_untrain_path = hof_response_dir + '/hof_obj_untrain.pkl'
        obj_train_list = pickle.load(open(obj_train_path,"rb"))
        obj_untrain_list = pickle.load(open(obj_untrain_path,"rb"))
        seed_list = pickle.load(open(hof_response_dir + '/seed_indices.pkl',"rb"))


        stim_file = 'preprocessed/StimMapReps.csv'
        stim_df = pd.read_csv(stim_file, sep='\s*,\s*',
                               header=0, encoding='ascii', engine='python')

        import exp_var_metric
        import copy

        dt = 1/200.0 # ms
        sigma = [10] # ms

        exp_variance_hof = []
        spiketimes_hof = []

        for ii,hof_response_all_proto in enumerate(hof_response_list):

            exp_variance_dict = {}
            peaktimes_model = {}

            if noise_bool:
                spike_times_exp_copy = copy.deepcopy(spike_times_exp_pkl)

                hof_response = {key:val for key,val in hof_response_all_proto[0].items() if 'Noise' in key}

                for noise_stim,noise_resp in hof_response.items():

                    noise_stim_name = noise_stim.split('.')[0]
                    noise_stim_type = noise_stim.rsplit('_',1)[0]

                    expt_trains = spike_times_exp_copy[noise_stim_name]

                    for i,exp_train in enumerate(expt_trains):
                        exp_train = [int(math.ceil(sp_time/dt)) for sp_time in exp_train]
                        expt_trains[i] = np.asarray(exp_train)


                    trace = {}
                    trace['T'] = noise_resp['time']
                    trace['V'] = noise_resp['voltage']
                    stim_start = stim_df.loc[stim_df.DistinctID == noise_stim_name,'Stim_Start'].values
                    stim_stop = stim_df.loc[stim_df.DistinctID == noise_stim_name,'Stim_End'].values
                    trace['stim_start'] = [stim_start[0]]
                    trace['stim_end'] = [stim_stop[0]]
                    model_train = efel.getFeatureValues(
                        [trace],
                        ['peak_time'])[0]['peak_time']
                    peaktimes_model[noise_stim_name] = copy.deepcopy(model_train)
                    for i,sp_time in enumerate(model_train):
                        model_train[i] = int(math.ceil(sp_time/dt))

                    model_train = model_train.astype(int)
                    sweep_filename = 'preprocessed/'+noise_stim_name+'.txt'
                    exp_data = np.loadtxt(sweep_filename)
                    exp_data_time = exp_data[:,0]
                    total_length = int(math.ceil(exp_data_time[-1]/dt))
                    exp_variance_dict[noise_stim_type] = exp_var_metric.calculate_spike_time_metrics(expt_trains,
                                model_train, total_length, dt, sigma)[0]

            objectives_train = obj_train_list[ii]
            feature_avg_train = np.mean(list(objectives_train.values()))
            feature_avg_untrain = np.mean(list(obj_untrain_list[ii].values()))
            avg_explained_variance = np.mean(list(exp_variance_dict.values()))
            exp_variance_dict['Feature_Average'] = feature_avg_train
            exp_variance_dict['Explained_Variance'] = avg_explained_variance
            exp_variance_dict['Feature_Average_Generalization'] = feature_avg_untrain
            exp_variance_dict['Seed'] = seed_list[ii]

            exp_variance_hof.append(copy.deepcopy(exp_variance_dict))
            if peaktimes_model:
                spiketimes_hof.append(copy.deepcopy(peaktimes_model))



        exp_variance_hof_path = 'Validation_Responses/exp_variance_hof.pkl'
        if not os.path.exists(os.path.dirname(exp_variance_hof_path)):
            try:
                os.makedirs(os.path.dirname(spiketimes_exp_path))
            except OSError as exc: # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise

        pickle.dump(exp_variance_hof,open(exp_variance_hof_path, 'wb'))

        if noise_bool:
            spiketimes_hof_path = 'Validation_Responses/spiketimes_model_noise.pkl'
            pickle.dump(spiketimes_hof,open(spiketimes_hof_path, 'wb'))


        validation_df = pd.DataFrame(exp_variance_hof)
        validation_df_shortened = validation_df.loc[:,['Explained_Variance',
                                                       'Feature_Average',
                                                       'Feature_Average_Generalization']]

        validation_df_shortened = validation_df_shortened.dropna(axis='columns')

        seed_index = validation_df.pop('Seed')
        lut = dict(zip(seed_index.unique(), "rbgy"))
        row_colors = seed_index.map(lut)
        validation_arr = validation_df_shortened.values
        sns.set(style="darkgrid", font_scale=.95)
        g=sns.clustermap(validation_df_shortened,col_cluster = False,
                       standard_scale=1)
        g=sns.clustermap(validation_df_shortened, annot = validation_arr[np.array(g.dendrogram_row.reordered_ind)],
                    col_cluster = False, row_colors=row_colors, standard_scale=1)

        g.fig.suptitle('Model Selection',fontsize = 14)


        pdf_pages.savefig(g.fig)
        plt.close(g.fig)


        if noise_bool:
            g = sns.lmplot(x="Feature_Average", y="Explained_Variance", data=validation_df)
            pdf_pages.savefig(g.fig)
            plt.close(g.fig)

        fitness_metrics = pd.DataFrame({'species' : [species],
                            'cell_id' : [cell_id],
                            'layer' : [layer],
                            'area' : [area],
                            'cre_line' : [cre_line],
                            'dendrite_type' : [dendrite_type],
                            'feature_avg_train' : [exp_variance_hof[0]['Feature_Average']],
                            'feature_avg_generalization' : [exp_variance_hof[0]['Feature_Average_Generalization']],
                            'feature_avg_released_allactive' : [feature_avg_released_allactive],
                            'feature_avg_peri' : [feature_avg_peri],
                            'explained_variance' : [exp_variance_hof[0]['Explained_Variance']],
                            'explained_variance_released_allactive' : [explained_variance_released_allactive],
                            'explained_variance_peri' : [explained_variance_peri],
                            })

        fitness_filename = 'Validation_Responses/fitness_metrics_'+cell_id+'.csv'
        fitness_metrics.to_csv(fitness_filename)
