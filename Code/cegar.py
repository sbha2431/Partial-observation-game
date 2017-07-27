__author__ = 'sudab'

import sys,os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gridworld import *
import belief_refinement
import grid_partition
import Slugs_input
import Salty_input
import subprocess
import time
import simulateController
import counterexample_parser

slugs = '/home/rayna/work/tools/slugs/src/slugs'

def cegar_loop(gwg,moveobstacles,beliefcons,beliefparts,infile,outfile,cexfile,belief_only):

    partition = grid_partition.partitionGrid(gwg,beliefparts);

    if not belief_only: # check realizability of the LTL specification under full observability
        print ('Writing slugs input file...')
        filename = 'slugs_input_'+str(gwg.nagents)+'agents.structuredslugs'
        Salty_input.write_to_slugs_fullobs(infile,gwg,moveobstacles[0])
        print ('Converting input file...')
        os.system('python compiler.py ' + infile + '.structuredslugs > ' + infile + '.slugsin')
        print('Checking realizability of LTL spec ...')
        sp = subprocess.Popen(slugs + ' --counterStrategy ' + infile+'.slugsin > ' + cexfile,shell=True, stdout=subprocess.PIPE)
        sp.wait()
    
        if (os.stat(cexfile).st_size > 0):
            print 'LTL specification is not realizable.'
            return 
        else:    
            print 'LTL specification is realizable.'
        
    done = False
    realizable = False
    iteration = 1
    
    while (not done):

        print 'ITERATION ', iteration
        print 'PARTITION', partition

        '''
        if not belief_only: # check realizability of the belief threshold spec
            print ('Writing slugs input file...')
            Salty_input.write_to_slugs_part(infile,gwg,moveobstacles[0],1, partition,beliefcons,True)
            print ('Converting input file...')
            os.system('python compiler.py ' + infile + '.structuredslugs > ' + infile + '.slugsin')
            print('Checking realizability of belief threshold spec...')
            subprocess.Popen(slugs + ' --counterStrategy ' + infile+'.slugsin > ' + cexfile,shell=True, stdout=subprocess.PIPE)
        '''
        
        # check realizability of the full spec
        print ('Writing slugs input file...')
        Salty_input.write_to_slugs_part(infile,gwg,moveobstacles[0],1, partition,beliefcons,belief_only)
        print ('Converting input file...')
        os.system('python compiler.py ' + infile + '.structuredslugs > ' + infile + '.slugsin')
        print('Checking realizability of full spec...')
        sp = subprocess.Popen(slugs + ' --counterStrategy ' + infile+'.slugsin > ' + cexfile,shell=True, stdout=subprocess.PIPE)
        sp.wait()
        
        done = (os.stat(cexfile).st_size == 0)
            
        if (done):
            realizable=True
            break;
    
        # check if counterexample is spurious
        
        (res_belief,leafBelief,toRefine_belief,res_ltl,belief_violated,toRefine_ltl) = belief_refinement.analyse_counterexample(cexfile,gwg,partition,beliefcons)
        
        if (belief_violated and not res_belief):
            print 'Belief constraint not realizable'
            break
            
        if((not res_belief) and (not res_ltl)):
            print 'No further refinement possible'
            break
        
        if res_belief: # refine belief abstraction using belief constraint
    
            print 'REFINING DUE TO BELIEF CONSTRAINT'
            
            # OLD REFINEMENT: based only on a leaf node in the tree 
            '''
            for k in refineLeaf:
            partition = grid_partition.partitionState_manual(partition,k,leafBelief)
            '''
            # OLD REFINEMENT: ends here
        
            # NEW REFINEMENT: propagating the refinement of the leaf backwards on the path
        
            refinement_map  = dict() # maps abstract partitions to lists or state sets with which to refine
            neg_states = set()       # set of states that are propagated backwards along the counterexample path
      
            '''
            initialize neg_states to be the set of states that are in the abstract belief, 
            but not in the most precise belief for the leaf node of the counterexample path
            '''
            Leaf = toRefine_belief.pop(0)
            for k in Leaf:
                neg_states = neg_states.union(partition[k].difference(leafBelief))
                refinement_map[k] = list()
                refinement_map[k].append(leafBelief)
            ''' 
            propagate the refinement information backwards along toRefine until
            a singleton belief or the root node of the tree is reached
            '''
            for tr in toRefine_belief:
                if not tr:
                    break
                neg_succ = neg_states
                neg_states = set()
                # propagate refinement set backwards
                for k in tr: 
                    for s in partition[k]:
                        for a in gwg.actlist:
                            t = set (np.nonzero(gwg.prob[a][s])[0]) #- set(gwg.obstacles)
                            #for ag in range(gwg.nagents):
                            #    for ta in gwg.targets[ag]:
                            #        t.discard(ta)
                            if t.intersection(neg_succ):
                                
                                neg_states.add(s)
                                
                # store set in refinement_map        
                for k in tr:
                    if k in refinement_map:
                        refinement_map[k].append(neg_states)
                    else:
                        refinement_map[k] = list()
                        refinement_map[k].append(neg_states)
            '''
            split each of the partitions k in refinement_map according to the
            list refinement_map[k] of sets of concrete states 
            '''
            for k in refinement_map.iterkeys():
                partition  = grid_partition.refine_partition(partition,k,refinement_map[k])
        
            # NEW REFINEMENT: ends here
        else: 
            if not belief_only: # refine belief abstraction for the LTL specification
                print 'REFINING DUE TO LTL SPECIFICATION'
                for k in toRefine_ltl.keys():
                    partition = grid_partition.refine_partition(partition,k,toRefine_ltl[k])
            else:
                break
        iteration = iteration+1

    if(not realizable):
        print('Specification is not realizable')
        print('Simulating counter-strategy ...')
        counterexample_parser.run_counterexample_part(cexfile,gwg,partition)
        
    else: 
        # compute controller for realizable abstraction

        Salty_input.write_to_slugs_part(infile,gwg,moveobstacles[0],1, partition,beliefcons,belief_only)
        print ('Converting input file...')
        os.system('python compiler.py ' + infile + '.structuredslugs > ' + infile + '.slugsin')
        print('Computing controller...')
        sp = subprocess.Popen(slugs + ' --explicitStrategy --jsonOutput ' + infile + '.slugsin > '+ outfile,shell=True, stdout=subprocess.PIPE)
        sp.wait()
        print('Simulating controller ...')
        
        simulateController.userControlled_partition(outfile,gwg,partition,moveobstacles)
        

