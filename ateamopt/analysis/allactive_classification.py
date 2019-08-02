import logging
from allensdk.core.cell_types_cache import CellTypesCache
import pandas as pd
from ateamopt.utils import utility
from ateamopt.analysis.optim_analysis import Optim_Analyzer
from functools import partial
from multiprocessing import Pool
import multiprocessing
import numpy as np
import os
from collections import defaultdict
from sklearn.preprocessing import StandardScaler,MinMaxScaler   
from sklearn.pipeline import Pipeline
from sklearn.manifold import TSNE
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier           
from sklearn.decomposition import PCA
from sklearn import preprocessing
from sklearn.metrics import classification_report,\
                 confusion_matrix,accuracy_score  
from sklearn.model_selection import train_test_split  
from sklearn.utils.multiclass import unique_labels     
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.cm import ScalarMappable
from matplotlib.colors import ListedColormap
from scipy.stats import iqr
from umap import UMAP
from matplotlib.ticker import MaxNLocator


from IPython import get_ipython
get_ipython().run_line_magic('matplotlib', 'inline')
 
logger = logging.getLogger(__name__)

marker_list = list(Line2D.markers.keys())[2:-4]

def reformat_legend(axes,sorted_class,color_list,marker_size):
    
    all_handles,all_labels,all_colors = [], [], []
    for i in range(axes.shape[0]):
        for j in range(axes.shape[1]):
            handles,labels = axes[i][j].get_legend_handles_labels()
            for handle_,label_ in zip(handles,labels):
                label_split = label_.split('.')[0]
                if  label_split not in all_labels:
                    all_labels.append(label_split)
                    all_handles.append(handle_)
                    all_colors.append(color_list[sorted_class.index(label_split)])
    
    dummy_handles = []
    for handle_,label_,color_ in zip(all_handles,all_labels,all_colors):
        h = plt.scatter([],[],marker = 'o',color = color_,s=marker_size,
                      label = label_)
        dummy_handles.append(h)
    
    return dummy_handles,all_labels


class Allactive_Classification(object):
    def __init__(self, param_file_list=None,metadata_file_list=None,
                     model_perf_filelist=None,me_cluster_data=None,
                     sdk_datapath=None,
                     efeature_file_list = None,
                     protocol_file_list = None,
                     morph_file_list = None,
                     species=None):
        self.species = species
        self.param_file_list = param_file_list
        self.metadata_file_list = metadata_file_list
        self.sdk_datapath = sdk_datapath
        self.me_cluster_data = me_cluster_data
        self.model_perf_filelist = model_perf_filelist
        self.efeature_file_list = efeature_file_list
        self.protocol_file_list = protocol_file_list
        self.morph_file_list = morph_file_list
    
    def allactive_param_data(self,repeat_params,save_data=False):
        analysis_handler = Optim_Analyzer()
        func = partial(analysis_handler.convert_aibs_param_to_dict,
                       repeat_params = repeat_params)
        p = Pool(multiprocessing.cpu_count())
        param_dict_list = p.map(func,self.param_file_list)
        p.close()
        p.join()
        param_df = pd.DataFrame(param_dict_list)
        if save_data:
            self.save_class_data(param_df,'allactive_params.csv',
                        'allactive_paramsdatatype.csv')
        return param_df
    
    def allactive_metadata(self,save_data=False):
        metadata_file_list = self.metadata_file_list
        metadata_list = []
        for metadata_file_ in metadata_file_list:
            metadata_list.append(utility.load_json(metadata_file_))
            
        metadata_df = pd.DataFrame(metadata_list)
        if save_data:
            self.save_class_data(metadata_df,'allactive_metadata.csv',
                        'allactive_metadatatype.csv')
        return metadata_df
        
    def morph_data(self,save_data=False):
        morph_file_list = self.morph_file_list
        morph_data_list = []
        for morph_file_ in morph_file_list:
            morph_dict = utility.load_json(morph_file_)
            cell_id = morph_file_.split('/')[-2]
            morph_dict['Cell_id'] = cell_id
            morph_data_list.append(morph_dict.copy())
         
        morph_df = pd.DataFrame(morph_data_list)   
        if save_data:
            self.save_class_data(morph_df,'morph_data.csv',
                        'morph_datatype.csv')
        return morph_df
    
    def sdk_data(self,save_data=False):
        if self.sdk_datapath and not os.path.exists(self.sdk_datapath):
            ctc = CellTypesCache()
            cells_allensdk = ctc.get_cells(species = [self.species],simple = False)
            cells_sdk_df = pd.DataFrame(cells_allensdk)
            cells_sdk_df.rename(columns={'specimen__id':'Cell_id'},inplace=True)
            cells_sdk_df['Cell_id'] = cells_sdk_df['Cell_id'].astype(str)
            if save_data:
                self.save_class_data(cells_sdk_df,self.sdk_datapath,
                                'sdk_datatype.csv')
        else:
            cells_sdk_df = self.read_class_data(self.sdk_datapath,
                                               'sdk_datatype.csv')
        return cells_sdk_df
    
    def me_data(self):
        me_cluster_data = self.me_cluster_data
        me_cluster_df = pd.read_csv(me_cluster_data,index_col=None)
        me_cluster_df.rename(columns={'specimen_id':'Cell_id'},inplace=True)
        me_cluster_df['Cell_id'] = me_cluster_df['Cell_id'].astype(str)
        return me_cluster_df
    
    def model_performance_data(self,save_data=False):
        metric_list_df = []
        model_perf_filelist = self.model_perf_filelist
        for metric_file_ in model_perf_filelist:
            cell_id= metric_file_.split('/')[-2]
            metric_list = utility.load_pickle(metric_file_)
            metric_dict = [{'hof_index' : ii, 'Feature_Avg_Train' : metric_list_['Feature_Average'],
                           'Feature_Avg_Generalization' : metric_list_['Feature_Average_Generalization'],
                           'Explained_Variance' : metric_list_['Explained_Variance'],
                           'Seed_Index' : metric_list_['Seed'],
                           'Cell_id' : cell_id} \
                           for ii,metric_list_ in enumerate(metric_list)]
            metric_list_df.extend(metric_dict)
        perf_metric_df = pd.DataFrame(metric_list_df)
        perf_metric_df['Explained_Variance'] *= 100
        
        if save_data:
            self.save_class_data(perf_metric_df,'performance_metric.csv',
                        'performance_datatype.csv')
        return perf_metric_df
    
    def broad_cre_lump_Pyr(self,cre_var):
        pyr_select_list = ['Scnn1a-Tg3-Cre','Nr5a1-Cre',
               'Rbp4-Cre_KL100','Rorb-IRES2-Cre','Cux2-CreERT2']
        if cre_var.startswith('Htr3a'):
            return 'Htr3a'
        elif cre_var.startswith('Pvalb'):
            return 'Pvalb'
        elif cre_var.startswith('Sst'):
            return 'Sst'
        elif cre_var in pyr_select_list:
            return 'Pyr'
        else:
            return None
    
    
    def ephys_data(self,save_data=False):
#        select_features = ['AHP_depth',
#                       'AP_amplitude_from_voltagebase',
#                       'AP_width',
#                       'voltage_base']
        efeature_file_list=sorted(self.efeature_file_list)
        protocol_file_list = sorted(self.protocol_file_list) 
#        features_list = []
#        for efeature_file in efeature_file_list:
#            cell_id = efeature_file.split('/')[-2]
#            ephys_features_dict = {'Cell_id':cell_id}
#            feature_dict = utility.load_json(efeature_file)
#            eFEL_features = self.get_eFEL_features(feature_dict,
#                                               select_features)
#            ephys_features_dict.update(eFEL_features)
#            features_list.append(ephys_features_dict.copy())
#        ephys_features_df = pd.DataFrame(features_list)
        
        
        ephys_dict_list = []
        for proto_file,efeature_file in zip(protocol_file_list,\
                                            efeature_file_list):
            cell_id = proto_file.split('/')[-2]
            proto_dict = utility.load_json(proto_file)
            proto_dict = {p_key:p_val['stimuli'][0]['amp'] for p_key,p_val\
                          in proto_dict.items()}
            sorted_proto_names = sorted(proto_dict,key=proto_dict.__getitem__)
            efeature_dict = utility.load_json(efeature_file)
            
            
            for sorted_proto in sorted_proto_names:
                if 'LongDC_' in sorted_proto:
                    ephys_dict = {'Cell_id':cell_id}
                    ephys_dict['stim_name'] = sorted_proto
                    ephys_dict['amp'] = proto_dict[sorted_proto]
                    if sorted_proto in efeature_dict.keys():
                        feat= efeature_dict[sorted_proto]['soma']
                        feat = {e_key:e_val[0] for e_key,e_val in feat.items()}
                        ephys_dict.update(feat)
                    ephys_dict_list.append(ephys_dict)
        
        ephys_df= pd.DataFrame(ephys_dict_list)  
        cell_ids = ephys_df.Cell_id.unique()
        efeat_max_amp_df= pd.concat([ephys_df.loc[ephys_df.Cell_id==cell_id,]\
                         .tail(1) for cell_id in cell_ids])
        
        return efeat_max_amp_df,ephys_df
        
    
    
    
    @staticmethod
    def get_data_fields(data_path):
        if isinstance(data_path,pd.DataFrame):
            return list(data_path)
        else:
            if data_path.endswith('.json'):
                json_data = utility.load_json(data_path) 
                return list(json_data.keys())
            elif data_path.endswith('.csv'):
                csv_data = pd.read_csv(data_path, index_col = None)
                return list(csv_data)
        
        logger.debug('Not in .json,.csv or pandas dataframe format')
        return None
    
    @staticmethod
    def save_class_data(data,data_filename,datatype_filename):
        data.dtypes.to_frame('types').to_csv(datatype_filename)
        data.to_csv(data_filename, index=None)
    
    @staticmethod    
    def read_class_data(data_filename,datatype_filename):
        datatypes = pd.read_csv(datatype_filename)['types']
        data = pd.read_csv(data_filename, dtype=datatypes.to_dict())
        return data
        
    # Get cell ids for optimization from ME data
    @staticmethod        
    def get_cellid_for_opt(df_L,df_S,target_field='cre',
                           addl_target = 'me_type',
                           non_std_morph_path=None,select_types=None):
        info_fields = ['cre','dendrite_type']
        select_fields = list(set([target_field, addl_target]+info_fields))
        select_fields = [select_field_ for select_field_ in select_fields \
                         if select_field_ is not None]
        df_L = df_L.dropna(subset=select_fields,how='any',axis=0)
        df_L_select = df_L.loc[:,['Cell_id']+select_fields]
        if select_types:
            df_L_select = df_L_select.loc[df_L_select[target_field].\
                                          isin(select_types),]
        
        df_L_cellids = df_L_select['Cell_id'].unique()
        df_S_cellids = df_S['Cell_id'].unique()
        
        if non_std_morph_path:
            non_std_morph_cells = pd.read_csv(non_std_morph_path,index_col=None)
            non_std_cell_ids = non_std_morph_cells.values
            df_S_cellids = np.append(df_S_cellids,non_std_cell_ids)
        cell_id_target = [cell_ for cell_ in df_L_cellids \
                          if cell_ not in df_S_cellids]
        df_L_select = df_L_select.loc[df_L_select['Cell_id'].\
                                      isin(cell_id_target),]
        df_L_select = df_L_select.reset_index(drop=True)
        return df_L_select
        
    @staticmethod    
    def get_data_stat(data,field='Cre_line',agg_field='me_type'):
        data_grouped = data.groupby(field)
        grouped_stat = data_grouped[agg_field].agg(np.size)
        return grouped_stat
        
    @staticmethod    
    def get_eFEL_features(feature_dict,select_features):
        eFEL_features= defaultdict(list)
        for feat_stim,feat_val in feature_dict.items():
            eFEL_feat = feat_val['soma']
            for key_,val_ in eFEL_feat.items():
                if key_ in select_features:
                    eFEL_features[key_].append(val_[0])
                    
        eFEL_features = {feat_key:np.mean(feat_val) \
                 for feat_key,feat_val in eFEL_features.items()}
        return eFEL_features
    
    
    @staticmethod
    def prepare_data_clf(data,feature_fields,target_field,
                         property_fields = [],
                         least_pop=5):
        
        data = data.loc[:,~data.columns.duplicated()]
        data_section = data.loc[:,feature_fields+property_fields+\
                                [target_field]] 
        
        # drop any cell with target field nan
        data_section = data_section.dropna(axis=0, how = 'any',
                               subset=[target_field] + property_fields)
        
        # filtering based on least populated class
        agg_data = data_section.groupby(target_field)[feature_fields[0]].\
                        agg(np.size).to_dict()
        filtered_targets = [key for key,val in agg_data.items() \
                            if val >= least_pop]
        data_section = data_section.loc[data_section[target_field].\
                        isin(filtered_targets),]
        
        # drop any feature which is nan for any cells
        data_section = data_section.dropna(axis =1,
                                           how = 'any')
        revised_features = [feature_field for feature_field in \
                    list(data_section) if feature_field in feature_fields]
        X_df = data_section.loc[:,revised_features + property_fields]
        y_df = data_section.loc[:,[target_field]]
        return X_df,y_df,revised_features
    
    @staticmethod    
    def SVM_classifier(X_df,y_df,feature_fields,
                       target_field,
                       plot_confusion_mat=False,
                       conf_mat_figname=None):
        
        
        clf = SVC(kernel='rbf')  
        svm_pipeline =  Pipeline([('scaler', StandardScaler()),
                                      ('svc', clf)])
        le = preprocessing.LabelEncoder()  
        y_df['label_encoder']= le.fit_transform(y_df[target_field])
        
        X_data = X_df.loc[:,feature_fields].values
        y_data = y_df['label_encoder'].values
        
        X_train, X_test, y_train, y_test = train_test_split(X_data, y_data,\
                        test_size=0.3, 
                        stratify=y_data, random_state=0)
        
        svm_pipeline.fit(X_train, y_train)
        y_pred_test = svm_pipeline.predict(X_test)
        confusion_matrix_svm = confusion_matrix(y_test, y_pred_test)
        svm_report = classification_report(y_test, y_pred_test)
        score = accuracy_score(y_test, y_pred_test)*100
        classes = le.inverse_transform(unique_labels(y_test, \
                                        y_pred_test))
        
        df_conf_svm = pd.DataFrame(confusion_matrix_svm, classes,
              classes)
        df_conf_svm=df_conf_svm.div(df_conf_svm.sum(axis=1),axis=0)
        
        if plot_confusion_mat:
            sns.set(style="whitegrid")
            fig = plt.figure(figsize=(4,3))
            cmap = sns.cubehelix_palette(light=1, as_cmap=True)
            ax = sns.heatmap(df_conf_svm,cmap=cmap,alpha=0.8,linewidths=.1,
                             linecolor='lightgrey',vmin=0,vmax=1)
            fig.suptitle('Accuracy: %s %%'%score, fontsize = 10)
            ax.set_ylabel('True Label',fontsize=8)
            ax.set_xlabel('Predicted Label',fontsize=8)
            plt.setp(ax.get_xticklabels(),fontsize=8,rotation=60,ha='right')
            plt.setp(ax.get_yticklabels(),fontsize=8)
            fig.savefig(conf_mat_figname,bbox_inches='tight')
            plt.close(fig)
        return score,confusion_matrix_svm,svm_report,df_conf_svm
            
    
    @staticmethod
    def RF_classifier(X_df,y_df,feature_fields,target_field,color_dict,
                  plot_confusion_mat=False,conf_mat_figname=None,
                  plot_feat_imp=False,feat_imp_figname=None,):
        clf = RandomForestClassifier(n_estimators=100, random_state=0)
        rf_pipeline = Pipeline([('scaler', StandardScaler()),
                                  ('random_forest', clf)])
        le = preprocessing.LabelEncoder()   
        y_df['label_encoder']= le.fit_transform(y_df[target_field])
        
        X_data = X_df.loc[:,feature_fields].values
        y_data = y_df['label_encoder'].values
        
        X_train, X_test, y_train, y_test = train_test_split(X_data, y_data,\
                        test_size=0.3, 
                        stratify=y_data, random_state=0)
        rf_pipeline.fit(X_train, y_train)
        y_pred_test = rf_pipeline.predict(X_test)
        
        confusion_matrix_rf = confusion_matrix(y_test, y_pred_test)
        rf_report = classification_report(y_test, y_pred_test)
        score = accuracy_score(y_test, y_pred_test)*100
        classes = le.inverse_transform(unique_labels(y_test, \
                                        y_pred_test))
        df_conf_rf= pd.DataFrame(confusion_matrix_rf, classes,
                  classes)
        df_conf_rf=df_conf_rf.div(df_conf_rf.sum(axis=1),axis=0)
        
        feature_imp = pd.Series(rf_pipeline.named_steps['random_forest'].feature_importances_,
                        index=feature_fields).sort_values(ascending=False)
        feature_fields_sorted = feature_imp.index.values
        feature_dict = {'importance': [], 'param_name' : []}
        for tree in rf_pipeline.named_steps['random_forest'].estimators_:
            for i, param_name_ in enumerate(feature_fields_sorted):
                sorted_idx = np.where(np.array(feature_fields) == param_name_)[0][0]
                feature_dict['importance'].append(tree.feature_importances_[sorted_idx])
                feature_dict['param_name'].append(param_name_)
        feature_imp_df = pd.DataFrame(feature_dict)
        
        
        if plot_confusion_mat:
            sns.set(style="whitegrid")
            fig = plt.figure(figsize=(4,3))
            
            cmap = sns.cubehelix_palette(light=1, as_cmap=True)
            ax = sns.heatmap(df_conf_rf,cmap=cmap,alpha=0.8,linewidths=.1,
                             linecolor='lightgrey',vmin=0,vmax=1)
            fig.suptitle('Accuracy: %s %%'%score, fontsize = 10)
            ax.set_ylabel('True Label',fontsize=8)
            ax.set_xlabel('Predicted Label',fontsize=8)
            plt.setp(ax.get_xticklabels(),fontsize=8,rotation=60,ha='right')
            plt.setp(ax.get_yticklabels(),fontsize=8)
            fig.savefig(conf_mat_figname,bbox_inches='tight')
            plt.close(fig)
        
        
        if plot_feat_imp:
            fig,ax = plt.subplots(1, figsize = (8,6))
            color_list = [color_dict[feature_field_] for feature_field_ in
                          feature_fields_sorted]
            
            feature_fields_cmap = [ckey for ckey in
                          color_dict.keys() if ckey in feature_fields_sorted]
            cmap_color_list = [color_dict[color_feat] for color_feat in 
                               feature_fields_cmap]
            my_cmap = ListedColormap(cmap_color_list)
            sm = ScalarMappable(cmap=my_cmap, norm=plt.Normalize(0,
                                     len(feature_fields_cmap)-1))
            sm.set_array([])
            ax = sns.barplot(x='param_name', y='importance', data= feature_imp_df,
                            order =feature_fields_sorted, 
                            palette=color_list,errwidth=1,ax = ax)
            ax.set_ylabel('Feature Importance Score')
            ax.set_xlabel('')
            ax.set_xticklabels(labels=feature_fields_sorted,
                               rotation=90,ha = 'center')
            cbar = plt.colorbar(sm,boundaries=np.arange(\
                                len(feature_fields_sorted)+1)-0.5)
            cbar.set_ticks(np.arange(len(feature_fields_cmap)))
            cbar.ax.set_yticklabels(feature_fields_cmap, fontsize=10)    
            fig.savefig(feat_imp_figname,bbox_inches='tight')
            plt.close(fig)
        
        
        return score,confusion_matrix_rf,rf_report,df_conf_rf,\
                feature_imp_df
        
    
    @staticmethod
    def umap_embedding(X_df,y_df,feature_fields,
                       target_field,marker_field='Cell_id',
                       col_var = None,figname='tsne_plot.pdf',
                       figtitle = '',
                       **kwargs):
        
        
        umap_pipeline = Pipeline([
                ('scaling', StandardScaler()), \
                     ('umap',UMAP())])
        X_data = X_df.loc[:,feature_fields].values
        le = preprocessing.LabelEncoder()   
        y_df['label_encoder']= le.fit_transform(y_df[target_field])
        y_data = y_df['label_encoder'].values
        
        umap_results = umap_pipeline.fit_transform(X_data)
        
        data = pd.concat([X_df,y_df],axis=1)
        data['x-umap'] = umap_results[:,0]
        data['y-umap'] = umap_results[:,1]
        data['hue_marker'] = data.apply(lambda x : \
                    x[target_field] +'.'+ x[marker_field], axis =1)
        
        sorted_target = sorted(list(data[target_field].unique()))
        sorted_marker = sorted(list(data[marker_field].unique()))
        sorted_hue_marker = sorted(list(data['hue_marker'].unique()))
        sorted_col = sorted(list(data[col_var].unique())) \
                    if col_var else None
        
#        current_palette = sns.color_palette()
        if kwargs.get('palette'):
            palette = kwargs.pop('palette')
        else:
            palette = sns.color_palette()
        color_list = sns.color_palette(palette,len(sorted_target))
        color_df_list = [color_list[sorted_target.index(hue_.split('.')[0])] \
                         for hue_ in sorted_hue_marker]
        
        marker_df_list = [marker_list[sorted_marker.index(hue_.\
                           split('.')[1])%len(marker_list)] \
                         for hue_ in sorted_hue_marker]
        
        if target_field == marker_field:
            marker_df_list = ['o']*len(marker_df_list)
        
        if kwargs.get('marker_size'):
            marker_size = kwargs['marker_size']
        else:
            marker_size = 10
            
        sns.set(style="whitegrid")
        g = sns.FacetGrid(data,
                          col=col_var,col_order=sorted_col, 
                          hue='hue_marker',hue_order = sorted_hue_marker,
                          palette=color_df_list, hue_kws=dict(marker=marker_df_list),                      
                          height=8,aspect= 1.1
                            )
        g = (g.map(plt.scatter, "x-umap", "y-umap",s=marker_size))
         
        axes = g.axes
        dummy_handles,all_labels = reformat_legend(axes,sorted_target,
                                           color_list,marker_size)
        for ax_ in axes.ravel():
#            ax_.grid(False)
            ax_.axis('off')
            ax_.get_xaxis().set_visible(False)
            ax_.axes.get_yaxis().set_visible(False)
        
        if kwargs.get('legend'):
            g.fig.tight_layout(rect=[0, 0.1, .95, 1])
            g.fig.legend(handles = dummy_handles, labels = all_labels,
                         fontsize=16, loc= 'lower center',ncol=4)
#        figtitle += ' (n=%s)'%len(data['Cell_id'].unique())
#        g.fig.suptitle(figtitle,fontsize=16)
#        

        g.fig.savefig(figname, bbox_inches='tight',dpi=100)
        plt.close(g.fig)    
    
    
    @staticmethod
    def tsne_embedding(X_df,y_df,feature_fields,
                       target_field,marker_field='Cell_id',
                       col_var = None,figname='tsne_plot.pdf',
                       figtitle = '',
                       **kwargs):
        
        tsne_pipeline = Pipeline([('scaling', StandardScaler()), \
                     ('tsne',TSNE(n_components=2,random_state =0))])
            
        X_data = X_df.loc[:,feature_fields].values
        tsne_results = tsne_pipeline.fit_transform(X_data)
        
        data = pd.concat([X_df,y_df],axis=1)
        data['x-tsne'] = tsne_results[:,0]
        data['y-tsne'] = tsne_results[:,1]
        data['hue_marker'] = data.apply(lambda x : \
                    x[target_field] +'.'+ x[marker_field], axis =1)
        
        sorted_target = sorted(list(data[target_field].unique()))
        sorted_marker = sorted(list(data[marker_field].unique()))
        sorted_hue_marker = sorted(list(data['hue_marker'].unique()))
        sorted_col = sorted(list(data[col_var].unique())) \
                    if col_var else None
        
#        current_palette = sns.color_palette()
        if kwargs.get('palette'):
            palette = kwargs.pop('palette')
        else:
            palette = sns.color_palette()
        color_list = sns.color_palette(palette,len(sorted_target))
        color_df_list = [color_list[sorted_target.index(hue_.split('.')[0])] \
                         for hue_ in sorted_hue_marker]
        
        marker_df_list = [marker_list[sorted_marker.index(hue_.\
                           split('.')[1])%len(marker_list)] \
                         for hue_ in sorted_hue_marker]
        
        if target_field == marker_field:
            marker_df_list = ['o']*len(marker_df_list)
        
        if kwargs.get('marker_size'):
            marker_size = kwargs['marker_size']
        else:
            marker_size = 10
            
        sns.set(style="whitegrid")
        g = sns.FacetGrid(data,
                          col=col_var,col_order=sorted_col, 
                          hue='hue_marker',hue_order = sorted_hue_marker,
                          palette=color_df_list, hue_kws=dict(marker=marker_df_list),                      
                          height=8,aspect= 1.1
                            )
        g = (g.map(plt.scatter, "x-tsne", "y-tsne",s=marker_size))
         
        axes = g.axes
        dummy_handles,all_labels = reformat_legend(axes,sorted_target,
                                           color_list,marker_size)
        for ax_ in axes.ravel():
#            ax_.grid(False)
            ax_.axis('off')
            ax_.get_xaxis().set_visible(False)
            ax_.axes.get_yaxis().set_visible(False)
        
        if kwargs.get('legend'):
            g.fig.tight_layout(rect=[0, 0.1, .95, 1])
            g.fig.legend(handles = dummy_handles, labels = all_labels,
                         fontsize=16, loc= 'lower center',ncol=4)
#        figtitle += ' (n=%s)'%len(data['Cell_id'].unique())
#        g.fig.suptitle(figtitle,fontsize=16)
#        

        g.fig.savefig(figname, bbox_inches='tight',dpi=100)
        plt.close(g.fig)
        
    @staticmethod
    def calc_param_dist(param_df):
        param_df = param_df.sort_values('hof_index')
        param_df = param_df.dropna(axis=1,how='all')
        nunique = param_df.apply(pd.Series.nunique)
        cols_to_drop = nunique[nunique == 1].index
        param_df = param_df.drop(cols_to_drop, axis=1)
        
        param_values = param_df.drop(labels='hof_index',\
                                     axis=1).values
       
        param_values = np.transpose(param_values)
        param_mean = np.mean(param_values,axis=1)
        vec_len = param_mean.shape[0]
        param_values_sub = (param_values - \
                            param_mean[:,None])/param_mean[:,None]
        sub_norm_vec = np.linalg.norm(param_values_sub,axis=0)
        sub_norm_total = np.sum(sub_norm_vec)/vec_len
        sub_norm_ratio = sub_norm_vec/vec_len
        dist_array = np.append(sub_norm_ratio,sub_norm_total)
        return dist_array
    
    
    def calc_param_separation(self,hof_param_df):
        hof_param_df = hof_param_df.dropna(how='any',axis=1)
        cell_ids = hof_param_df.Cell_id.unique()
        param_df_list = [hof_param_df.loc[hof_param_df.Cell_id == cell_id,]\
                         for cell_id in cell_ids]
#        self.calc_param_dist(param_df_list[0])
        p = Pool(multiprocessing.cpu_count())
        param_dist_list = p.map(self.calc_param_dist,param_df_list)
        p.close()
        p.join()
        return param_dist_list
        
    @staticmethod
    def calc_obj_all(all_obj_file_list):
        obj_dict_list = [] 
        for obj_file in all_obj_file_list:
            obj_dict = utility.load_pickle(obj_file)
            cell_id = obj_file.split('/')[-2]
            for ii,obj_dict_ in enumerate(obj_dict):
                hof_obj_dict = {'Cell_id':cell_id,
                                'hof_index' : ii}
                hof_obj_dict['Feature_Avg'] = np.mean([val for val in obj_dict_.\
                            values()])
                obj_dict_list.append(hof_obj_dict)
        hof_obj_df = pd.DataFrame(obj_dict_list)
        return hof_obj_df
    

    @staticmethod
    def agg_model_features(model_feature_file_list,max_train_amp_dict):
        model_feat_dict_list = []
        for model_feat_file in model_feature_file_list:
            model_feat_dict = utility.load_pickle(model_feat_file)
            cell_id = model_feat_file.split('/')[-2]
            select_stim = max_train_amp_dict[cell_id]
            for ii,feat_dict_ in enumerate(model_feat_dict):
                hof_feat_dict = {'Cell_id':cell_id,
                                'hof_index' : ii}
                select_stim_feat = {key.split('.')[-1]:val for key,val in \
                        feat_dict_.items() if select_stim in key}
                hof_feat_dict.update(select_stim_feat)
                model_feat_dict_list.append(hof_feat_dict)
                
        return pd.DataFrame(model_feat_dict_list)
    
    @staticmethod
    def get_fi_slope(stim_fi, spike_fi):
        try:
            spiking_stim_idx = [ix for ix,rate in enumerate(spike_fi)\
                                   if rate > 0]
            stim_fi = np.array(stim_fi)[spiking_stim_idx]
            spike_fi = np.array(spike_fi)[spiking_stim_idx]
            x = np.array(stim_fi)*1e3
            y = np.array(spike_fi)
            A = np.vstack([x, np.ones_like(x)]).T
            m, _ = np.linalg.lstsq(A, y)[0]
            return m
        except:
            return None
        

    @staticmethod
    def get_fi_intercept(stim_fi, spike_fi):
        nonspiking_stim_idx = [ix for ix,rate in enumerate(spike_fi) if rate ==0]
        non_spiking_stim = [stim for idx,stim in enumerate(stim_fi) \
                if idx in nonspiking_stim_idx and stim > 0]
        try:
            intercept = non_spiking_stim[-1]
            return intercept*1e3  
        except:
            spiking_stim_idx = [ix for ix,rate in enumerate(spike_fi) if rate > 0]
            spiking_stim = [stim for idx,stim in enumerate(stim_fi) \
                if idx in spiking_stim_idx and stim > 0]
            intercept=spiking_stim[0]
            return intercept*1e3  
    
    
    def get_fI_prop(self,fi_data_file):
        if type(fi_data_file) is tuple:
            cell_id = fi_data_file[0].split('_')[-1].split('.')[0]
            data_dict = {'Cell_id' : cell_id}
            label_list = {'exp':'exp', 'aa' : 'All_active',
                           'peri' : 'Perisomatic'}
            for fi_file in fi_data_file:
                fi_data = utility.load_pickle(fi_file)
                data_type = fi_file.split('/')[-1].split('_')[1]
                data_type = label_list[data_type]
                stim_key = [key for key in fi_data.keys() \
                                if 'stim' in key][0]
                freq_key = [key for key in fi_data.keys() \
                                if 'freq' in key][0]
                slope_ = self.get_fi_slope(fi_data[stim_key],fi_data[freq_key])
                icpt_ = self.get_fi_intercept(fi_data[stim_key],fi_data[freq_key])
                data_dict['slope_{}'.format(data_type)] = slope_
                data_dict['intercept_{}'.format(data_type)] = icpt_
        else:
            fi_data = utility.load_pickle(fi_data_file)
            cell_id = fi_data_file.split('_')[-1].split('.')[0]
            data_dict = {'Cell_id' : cell_id}
            stim_keys = sorted([key for key in fi_data.keys() \
                                if 'stim' in key])
            freq_keys = sorted([key for key in fi_data.keys() \
                                if 'freq' in key])
            for stim,freq in zip(stim_keys,freq_keys):
                data_type = stim.split('_',1)[1]
                slope_ = self.get_fi_slope(fi_data[stim],fi_data[freq])
                icpt_ = self.get_fi_intercept(fi_data[stim],fi_data[freq])
                data_dict['slope_{}'.format(data_type)] = slope_
                data_dict['intercept_{}'.format(data_type)] = icpt_
                
        return data_dict
    
    @staticmethod
    def compare_fI_prop(fi_data_df,figname='fI_metric_comparison.pdf'):
        utility.create_filepath(figname)
        slope_exp = fi_data_df.slope_exp.values
        slope_aa = fi_data_df.slope_All_active.values
        slope_peri = fi_data_df.loc[fi_data_df['slope_Perisomatic'].\
                                        notnull(),'slope_Perisomatic'].values
        slope_exp_peri = fi_data_df.loc[fi_data_df['slope_Perisomatic'].\
                                        notnull(),'slope_exp'].values
        
        max_slope = max(max(slope_exp), max(slope_aa), 
                            max(slope_peri))+.1                               
                                        
        icpt_exp = fi_data_df.intercept_exp.values
        icpt_aa = fi_data_df.intercept_All_active.values
        icpt_peri = fi_data_df.loc[fi_data_df['intercept_Perisomatic'].\
                                   notnull(),'intercept_Perisomatic'].values
        icpt_exp_peri = fi_data_df.loc[fi_data_df['intercept_Perisomatic'].\
                                   notnull(),'intercept_exp']

        
        sns.set(style="whitegrid", font_scale=1)
        fig,(ax1,ax2) = plt.subplots(1,2,figsize = (6,3.5))
        ax1.plot([0,max_slope], [0,max_slope], color = 'k', lw = .5)
        sc_aa=ax1.scatter(slope_exp, slope_aa, color = 'b', 
                    s = 50, alpha = 0.5, lw = 0,label='All-active')
        sc_peri=ax1.scatter(slope_exp_peri, slope_peri, color = 'r', 
                    s = 50, alpha = 0.5, lw = 0,label='Perisomatic')

        ax1.set_xlabel('$Hz \:pA^{-1}$')
        ax1.set_ylabel('$Hz \:pA^{-1}$')
        ax1.set_title('fi slope')
        
        max_intercept = max(max(icpt_exp), max(icpt_aa), 
                            max(icpt_peri))+10
        ax2.plot([0,max_intercept], [0,max_intercept], color = 'k', lw = .5)
        ax2.scatter(icpt_exp, icpt_aa, color = 'b', 
                    s = 50, alpha = 0.5, lw = 0)
        ax2.scatter(icpt_exp_peri, icpt_peri, color = 'r',
                    s = 50, alpha = 0.5, lw = 0)
        
        ax2.set_xlabel('$I_{inj} \:(pA)$')
        ax2.set_ylabel('$I_{inj} \:(pA)$')
        ax2.set_title('Rheobase')
        
        handles = [sc_aa,sc_peri]
        labels = [h.get_label() for h in handles]
        fig.legend(handles = handles, labels=labels, \
                        loc = 'lower center', ncol=2)
        
        fig.tight_layout(rect=[0, 0.05, 1, 0.95])
        fig.savefig(figname,bbox_inches = 'tight')
        plt.close(fig)
    
    def plot_fi_curve(self,fi_curve_filelist,data_df,figname='fi_curve.pdf'):
        utility.create_filepath(figname)
        sns.set(style="whitegrid", font_scale=1)
        fig,ax = plt.subplots(2,3,figsize = (8,6),sharey='row')
        l_exp,l_aa,l_peri = [],[],[]
        for fi_data_file in fi_curve_filelist:
            if type(fi_data_file) is tuple:
                col_list = {'exp':'k', 'aa' : 'b', 'peri' : 'r'}
                column_list = {'exp':0, 'aa' : 1, 'peri' : 2}
                label_list = {'exp':'Experiment', 'aa' : 'All-active', 'peri' : 'Perisomatic'}
                cell_id = fi_data_file[0].split('_')[-1].split('.')[0]
                cell_type = self.get_celltype(cell_id,data_df) 
                if cell_type == 'unknown':
                    continue
                row_idx = 0 if cell_type == 'exc' else 1 
                for fi_file in fi_data_file:
                    fi_data = utility.load_pickle(fi_file)
                    data_type = fi_file.split('/')[-1].split('_')[1]
                    stim_key = [key for key in fi_data.keys() \
                                    if 'stim' in key][0]
                    freq_key = [key for key in fi_data.keys() \
                                    if 'freq' in key][0]
                    column_idx = column_list[data_type]
                    l, = ax[row_idx,column_idx].plot(fi_data[stim_key],\
                           fi_data[freq_key], color=col_list[data_type], 
                              alpha = 0.5,label=label_list[data_type])
                            
                    if data_type == 'exp':
                        l_exp.append(l)
                    elif data_type == 'aa':
                        l_aa.append(l)
                    else:
                        l_peri.append(l)
                                

            else:
                fi_data = utility.load_pickle(fi_data_file)
                col_list = {'exp':'k', 'All_active' : 'b',
                            'Perisomatic' : 'r'}
                column_list = {'exp':0, 'All_active' : 1, 'Perisomatic' : 2}
                cell_id = fi_data_file.split('_')[-1].split('.')[0]
                cell_type = self.get_celltype(cell_id,data_df) 
                if cell_type == 'unknown':
                    continue
                row_idx = 0 if cell_type == 'exc' else 1 
                stim_keys = sorted([key for key in fi_data.keys() \
                                if 'stim' in key])
                freq_keys = sorted([key for key in fi_data.keys() \
                                if 'freq' in key])
                for stim,freq in zip(stim_keys,freq_keys):
                    data_type = stim.split('_',1)[1]
                    column_idx = column_list[data_type]
                    ax[row_idx,column_idx].plot(fi_data[stim],fi_data[freq],
                      color=col_list[data_type], alpha = 0.5)
                    
        
        
        handles = [l_exp[0],l_aa[0],l_peri[0]]
        labels = [h.get_label() for h in handles]
        fig.legend(handles = handles, labels=labels, \
                        loc = 'lower center', ncol=3)
        fig.tight_layout(rect=[0, 0.05, 1, 0.95])
        fig.savefig(figname,bbox_inches='tight')
        plt.close(fig)

            

     
    @staticmethod
    def get_celltype(cell_id,data_df):
        cell_type_data = data_df.loc[(data_df.Cell_id == cell_id) &\
                   (data_df.hof_index == 0),                  
                 ['me_type','ephys_cluster','Dendrite_type']].reset_index()
        me_type = cell_type_data.at[0,'me_type']
        e_type = cell_type_data.at[0,'ephys_cluster'] 
        dend_type = cell_type_data.at[0,'Dendrite_type']
        try:
            one_word_type = me_type+'.'+ e_type+'.'+ dend_type
        
            if 'Exc' in one_word_type:
                return 'exc'
            elif 'Inh' in one_word_type:
                return 'inh'                     
            elif '.spiny' in one_word_type:
                return 'exc'
            elif '.spiny' in one_word_type:
                return 'inh'
            else:
                return 'unknown'
        except:
            return 'unknown'
    
    def plot_AP_shape(self,AP_shape_filelist,data_df,figname='AP_shape.pdf'):
        utility.create_filepath(figname)
        sns.set(style="whitegrid", font_scale=1)
        fig,ax = plt.subplots(2,3,figsize = (8,6), sharey='row')
        l_exp,l_aa,l_peri = [],[],[]
        
        for AP_shape_file in AP_shape_filelist:
            if type(AP_shape_file) is tuple:
                col_list = {'exp':'k', 'aa' : 'b', 'peri' : 'r'}
                column_list = {'exp':0, 'aa' : 1, 'peri' : 2}
                label_list = {'exp':'Experiment', 'aa' : 'All-active', 'peri' : 'Perisomatic'}
                cell_id = AP_shape_file[0].split('_')[-1].split('.')[0]
                cell_type = self.get_celltype(cell_id,data_df) 
                if cell_type == 'unknown':
                    continue
                row_idx = 0 if cell_type == 'exc' else 1 
                for file_ in AP_shape_file:
                    AP_data = utility.load_pickle(file_)
                    time_data = AP_data['time']
                    data_type = file_.split('/')[-1].split('_')[2]
                    for key,val in AP_data.items():
                        if 'time' not in key:              
                            spike_shape_data = val
                            column_idx = column_list[data_type]
                            l, = ax[row_idx,column_idx].plot(time_data,\
                              spike_shape_data, color=col_list[data_type], 
                              alpha = 0.5,label=label_list[data_type])
                            
                            if data_type == 'exp':
                                l_exp.append(l)
                            elif data_type == 'aa':
                                l_aa.append(l)
                            else:
                                l_peri.append(l)
                                

            else:
                AP_data = utility.load_pickle(AP_shape_file)
                col_list = {'exp':'k', 'All_active' : 'b',
                            'Perisomatic' : 'r'}
                column_list = {'exp':0, 'All_active' : 1, 'Perisomatic' : 2}
                cell_id = AP_shape_file.split('_')[-1].split('.')[0]
                cell_type = self.get_celltype(cell_id,data_df) 
                if cell_type == 'unknown':
                    continue
                row_idx = 0 if cell_type == 'exc' else 1 
                stim_names = sorted(list(set([key.split('_')[0]+'_'+key.split('_')[1]\
                              for key in AP_data.keys()])))
                for stim_name in stim_names:
                    time_data = AP_data[stim_name+'_time']
                    for data_type in col_list.keys():
                        try:
                            spike_shape_data = AP_data[stim_name+'_'+data_type]
                            column_idx = column_list[data_type]
                            ax[row_idx,column_idx].plot(time_data,\
                              spike_shape_data, color=col_list[data_type], alpha = 0.5)
                        except:
                            pass
        
        
        handles = [l_exp[0],l_aa[0],l_peri[0]]
        labels = [h.get_label() for h in handles]
        fig.legend(handles = handles, labels=labels, \
                        loc = 'lower center', ncol=3)
        for ax_ in ax:
            ax_.grid(False)
        fig.tight_layout(rect=[0, 0.05, 1, 0.95])
        fig.savefig(figname,bbox_inches='tight')
        plt.close(fig)
    

    @staticmethod
    def compare_ephys_prop(efeature,efeaure_df,
                           figname='efeature_comparison.pdf',
                           axis_label='',
                           title= '',**kwargs):
        utility.create_filepath(figname)
        select_df = efeaure_df.loc[efeaure_df.feature == \
                           efeature,]
        efeature_aa = select_df.loc[select_df.value_aa.notnull(),
                                  'value_aa'].values
        efeature_exp_aa = select_df.loc[select_df.value_aa.notnull(),\
                                  'value_exp'].values
        efeature_exp_peri = select_df.loc[select_df.value_peri.notnull(),\
                                  'value_exp'].values
        
        efeature_peri = select_df.loc[select_df.value_peri.notnull(),\
                                  'value_peri'].values
        max_efeature_amp = max(max(efeature_aa), max(efeature_exp_aa),
                       max(efeature_exp_peri),max(efeature_peri))
        min_efeature_amp = min(min(efeature_aa), min(efeature_exp_aa),
                       min(efeature_exp_peri),min(efeature_peri))
        median_efeature = np.median(select_df['value_exp'].values)
        feature_iqr = iqr(select_df['value_exp'].values)
        
        plt.style.use('seaborn-whitegrid')
        fig,ax = plt.subplots(figsize=(5,5),dpi=100)
        ax.plot([min_efeature_amp,max_efeature_amp], [min_efeature_amp,max_efeature_amp],
                 color = 'k', lw = .5)
        scat_peri= ax.scatter(efeature_exp_peri, efeature_peri, color = 'r', 
                    s = 40, alpha = 0.5, lw = 0,label='Perisomatic')
        scat_aa=ax.scatter(efeature_exp_aa, efeature_aa, color = 'b', 
                    s = 40, alpha = 0.5, lw = 0,label='All-active')
        
        xlim_minus,xlim_plus = max(median_efeature-5*feature_iqr,\
                min_efeature_amp),min(median_efeature+5*feature_iqr,\
                            max_efeature_amp)    
        ax.grid(False)
        xaxis_label = 'Experiment ' + axis_label \
                    if efeature != 'AP_amplitude_from_voltagebase' \
                        else 'Experiment \n' + axis_label
        yaxis_label = 'Model ' + axis_label \
                if efeature != 'AP_amplitude_from_voltagebase' \
                        else 'Model \n' + axis_label
        ax.set_xlabel(xaxis_label,fontsize=18)
        ax.set_ylabel(yaxis_label,fontsize=18)
        ax.locator_params(nbins=3, axis='x')
        ax.locator_params(nbins=3, axis='y')

        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
#        if title != '':
#            ax.set_title(title,fontsize=18)
#        else:
#            ax.set_title(efeature,fontsize=18)
            
        if efeature != 'Rheobase':   
            ax.set_xlim([xlim_minus,xlim_plus])
            ax.set_ylim([xlim_minus,xlim_plus])
            
#        ax.set_frame_on = False
        handles = [scat_aa,scat_peri]
        labels = [h.get_label() for h in handles]

        if kwargs.get('legend'):
            fig.legend(handles = handles, labels=labels, \
                            loc = 'lower center', ncol=2,fontsize=18)
            fig.tight_layout(rect=[0, 0.05, 1, 0.95])
        
        plt.setp(ax.get_xticklabels(),fontsize=16)
        plt.setp(ax.get_yticklabels(),fontsize=16)
        fig.savefig(figname,bbox_inches = 'tight')
        plt.close(fig)
    
    @staticmethod
    def compare_AP_prop(AP_data_df,figname='AP_metric_comparison.pdf'):
        utility.create_filepath(figname)
        AP_amp_df = AP_data_df.loc[AP_data_df.feature == \
                           'AP_amplitude_from_voltagebase',]
        AP_width_df = AP_data_df.loc[AP_data_df.feature == \
                           'AP_width',]
        AP_amp_aa = AP_amp_df.loc[AP_amp_df.value_aa.notnull(),
                                  'value_aa'].values
        AP_amp_exp_aa = AP_amp_df.loc[AP_amp_df.value_aa.notnull(),\
                                  'value_exp'].values
        AP_amp_exp_peri = AP_amp_df.loc[AP_amp_df.value_peri.notnull(),\
                                  'value_exp'].values
        
        AP_amp_peri = AP_amp_df.loc[AP_amp_df.value_peri.notnull(),\
                                  'value_peri'].values
        max_AP_amp = max(max(AP_amp_aa), max(AP_amp_exp_aa), max(AP_amp_exp_peri),
                            max(AP_amp_peri))+10                              
                                        
        AP_width_aa = AP_width_df.loc[AP_width_df.value_aa.notnull(),
                                  'value_aa'].values
        AP_width_exp_aa = AP_width_df.loc[AP_width_df.value_aa.notnull(),\
                                  'value_exp'].values
        AP_width_exp_peri = AP_width_df.loc[AP_width_df.value_peri.notnull(),\
                                  'value_exp'].values
        
        AP_width_peri = AP_width_df.loc[AP_width_df.value_peri.notnull(),\
                                  'value_peri'].values
        max_AP_width = max(max(AP_width_aa), max(AP_width_exp_aa), max(AP_width_exp_peri),
                            max(AP_width_peri))+.1         

        
        sns.set(style="whitegrid", font_scale=1)
        fig,(ax1,ax2) = plt.subplots(1,2,figsize = (6,3.5))
        ax1.plot([50,max_AP_amp], [50,max_AP_amp], color = 'k', lw = .5)
        AP_amp_aa=ax1.scatter(AP_amp_exp_aa, AP_amp_aa, color = 'b', 
                    s = 20, alpha = 0.5, lw = 0,label='All-active')
        AP_amp_peri= ax1.scatter(AP_amp_exp_peri, AP_amp_peri, color = 'r', 
                    s = 20, alpha = 0.5, lw = 0,label='Perisomatic')

        ax1.set_xlabel('$mV$')
        ax1.set_ylabel('$mV$')
        ax1.set_title('AP amplitude')

        ax2.plot([0,max_AP_width], [0,max_AP_width], color = 'k', lw = .5)
        ax2.scatter(AP_width_exp_aa, AP_width_aa, color = 'b', 
                    s = 20, alpha = 0.5, lw = 0)
        ax2.scatter(AP_width_exp_peri, AP_width_peri, color = 'r',
                    s = 20, alpha = 0.5, lw = 0)
        
        ax2.set_xlabel('$ms$')
        ax2.set_ylabel('$ms$')
        ax2.set_title('AP width')
        
        handles = [AP_amp_aa,AP_amp_peri]
        labels = [h.get_label() for h in handles]
        fig.legend(handles = handles, labels=labels, \
                        loc = 'lower center', ncol=2)
        
        fig.tight_layout(rect=[0, 0.05, 1, 0.95])
        fig.savefig(figname,bbox_inches = 'tight')
        plt.close(fig)
    
    @staticmethod
    def exp_features_to_dict(exp_feature_file):
        exp_feature_dict = utility.load_json(exp_feature_file)
        cell_id = exp_feature_file.split('/')[-2]
        final_dict={}
        for exp_stim,exp_feat_dict in exp_feature_dict.items():
            for key,val in exp_feat_dict['soma'].items():
                stim_loc_feat = '{stim}.{loc}.{feat}'.format(stim=exp_stim,
                                 loc='soma',feat=key)
                final_dict[stim_loc_feat] = val[0]
        
        return (final_dict,cell_id)
    
        
