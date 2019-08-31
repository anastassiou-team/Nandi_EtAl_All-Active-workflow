import argschema as ags
import efel

efel.getFeatureNames()

class Top_JobConfig(ags.schemas.DefaultSchema):
    job_dir = ags.fields.Str(description="")
    conda_env = ags.fields.Str(description="")
    nwb_path = ags.fields.Str(description="")
    swc_path = ags.fields.Str(description="")
    nwb_type = ags.fields.Str(description="")
    axon_type = ags.fields.Str(description="")
    ephys_dir = ags.fields.Str(description="")
    non_standard_nwb = ags.fields.Boolean(description="")
    acceptable_stimtypes = ags.fields.List(ags.fields.Str,description="")
    feature_names_path = ags.fields.InputFile(description="")
    email = ags.fields.List(ags.fields.Email,description="",required=False) 
    stimmap_file = ags.fields.Str(description="")
    machine = ags.fields.Str(description="")
    log_level = ags.fields.LogLevel(description='',default='DEBUG')
    all_features_path = ags.fields.Str(description="",required=False)
    all_protocols_path =ags.fields.Str(description="",required=False)
    dryrun = ags.fields.Boolean(default=False,
        description='Run a small optimization for testing')
    script_repo_dir = ags.fields.InputDir(description="",required=False)
    modfiles_dir = ags.fields.InputDir(description="",required=False)
    compiled_modfiles_dir = ags.fields.InputDir(description="",required=False)

class Stage_JobConfig(ags.schemas.DefaultSchema):
    stage_name = ags.fields.Str(description="")
    qos = ags.fields.Str(description="")
    stage_stimtypes = ags.fields.List(ags.fields.Str,description="")
    filter_rule =  ags.fields.Str(description="")
    stim_selection = ags.fields.Str(description="")
    stage_features = ags.fields.InputFile(description="")
    stage_parameters = ags.fields.InputFile(description="")
    cp_dir =  ags.fields.Str(description="",default='checkpoints')
    cp_backup_dir =  ags.fields.Str(description="",default=None,allow_none=True)
    cp_backup_frequency = ags.fields.Int(description="Checkpoint backup frequency",
                                         default=5)
    ipyp_optim = ags.fields.Boolean(description="",default=True)
#    compile_mech = ags.fields.Boolean(description="",default=True)
    offspring_size = ags.fields.Int(description="number of individuals in offspring",
                                    default=2)
    max_ngen = ags.fields.Int(description='maximum number of generations',
                              default=2)
    seed = ags.fields.List(ags.fields.Int,description="")
    timeout = ags.fields.Int(description="Simulation cut-off time in seconds",
                             default=900)
    learn_eval_trend = ags.fields.Boolean(default=False,
        description='Modify the timeout based on evaluation\
        times of previous generation (Experimental)')
    
    nengines = ags.fields.Int(description="no. of ipyparallel engines")
    nengines_analysis = ags.fields.Int(description="no. of ipyparallel engines")
    error_stream = ags.fields.Str(description="Direct error stream (PBS specific)") #'/dev/null'
    output_stream = ags.fields.Str(description="Direct output stream (PBS specific)")
    jobmem = ags.fields.Str(description="PBS specific")
    jobtime = ags.fields.Str(description="")#'00:30:00'
    jobtime_analysis = ags.fields.Str(description="")#'00:30:00'
    nnodes = ags.fields.Int(description="")
    nnodes_analysis = ags.fields.Int(description="")
    nprocs = ags.fields.Int(description="")
    nprocs_analysis = ags.fields.Int(description="")
    ipyp_db = ags.fields.OptionList(description="",options=['nodb','sqlitedb'])
    main_script = ags.fields.Str(description="",default='Optim_Main.py')
    analysis_script = ags.fields.Str(description="",default='analyze_stagejob.py')
    run_peri_comparison = ags.fields.Boolean(description="",default=False)
    run_released_aa_comparison = ags.fields.Boolean(description="",default=True)
    ipyp_analysis = ags.fields.Boolean(description="",default=False)
    run_hof_analysis = ags.fields.Boolean(description="",default=False)
#    run_ap_comparison = ags.fields.Boolean(description="",default=False)
#    run_fi_comparison = ags.fields.Boolean(description="",default=False)
    calc_model_perf = ags.fields.Boolean(description="",default=False)
    model_postprocess = ags.fields.Boolean(description="",default=False)
    calc_time_statistics = ags.fields.Boolean(description="",default=False)
    
class JobConfig(ags.schemas.DefaultSchema):
    highlevel_jobconfig = ags.fields.Nested(Top_JobConfig)
    stage_jobconfig = ags.fields.Nested(Stage_JobConfig,many=True)

class CtyConfig(ags.schemas.DefaultSchema):
    cell_id = ags.fields.Str(description="")
    e_type = ags.fields.Str(description="")
    me_type = ags.fields.Str(description="")
        
class Launch_Config(ags.ArgSchema):
    cty_config = ags.fields.Nested(CtyConfig,
                  description="Pass in the cell-specific information")
    log_level = ags.fields.LogLevel(description='Set log level',default='DEBUG')
    job_config = ags.fields.Nested(JobConfig,description="Stage level Job configuration")
    
    
class Stage_Launch_Config(ags.ArgSchema):
    highlevel_jobconfig = ags.fields.Nested(Top_JobConfig)
    stage_jobconfig = ags.fields.Nested(Stage_JobConfig)
    
class Optim_Config(ags.ArgSchema):
    highlevel_jobconfig = ags.fields.Nested(Top_JobConfig)
    stage_jobconfig = ags.fields.Nested(Stage_JobConfig)
    seed = ags.fields.Int(description='',
                              default=1)
    parameters = ags.fields.InputFile(description="")
    mechanism = ags.fields.InputFile(description="")
    released_aa_mechanism = ags.fields.InputFile(description="",required=False,
                                             allow_none=True)
    train_features = ags.fields.InputFile(description="")
    test_features= ags.fields.InputFile(description="")
    train_protocols= ags.fields.InputFile(description="")
    released_aa_model_dict = ags.fields.Dict(description="",required=False,
                                           allow_none=True)
#    released_peri_model_dict = ags.fields.Dict(description="",required=False,
#                                           allow_none=True)
    released_aa_model =  ags.fields.InputFile(description="",required=False,
                                           allow_none=True)
    released_peri_model =  ags.fields.InputFile(description="",required=False,
                                           allow_none=True)   
    released_peri_mechanism = ags.fields.InputFile(description="",required=False,
                                           allow_none=True)   
    
    
    
    