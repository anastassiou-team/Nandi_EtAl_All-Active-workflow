#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 31 13:54:54 2018

@author: anin
"""

import json

passive_and_Ih_params = {   
                'cm' : {'section' : ['soma', 'apic', 'dend', 'axon'],
                          'bounds':{'soma':[1e-1,5], 'apic':[1e-1,5], 'dend' : [1e-1,5],
                                    'axon':[1e-1,5]},
                        },
                'Ra' : {'section' : ['all'],
                        'bounds' : {'all':[50, 600]}
                        },
                'g_pas' : {'section' : ['all'],
                        'bounds' : {'all':[1e-7, 1e-2]}
                        },
                'e_pas' : {'section' : ['all'],
                        'bounds' : {'all':[-110, -70]}
                        },
                'gbar_HCN' : {'section' : ['soma', 'apic', 'dend'],
                        'mechanism': 'HCN',
                        'bounds' : {'soma':[1e-7,1e-4], 'apic':[1e-7, 1e-4], 'dend' : [1e-7,1e-4]}
                        },
                }



def main():
    with open('passive_and_Ih_bounds.json','w') as bound_file:
        json.dump(passive_and_Ih_params,bound_file,indent=4)   
        
        
if __name__ == '__main__':
    main()