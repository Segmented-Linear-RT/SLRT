#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Wen Jan 23 12:17:51 2019

@author: zhengxiangyu
"""



import scipy
import scipy.optimize
import scipy.stats
import numpy
import copy
import random
import math
from bisect import bisect_right
import pandas as pd


class Tree(object):
    def __init__(self, error, predict, stdev, start, num_points, var_value,\
                 var_dis, var_res, index, region_info):
        self.error = error
        self.predict = predict
        self.stdev = stdev
        self.start =  start
        self.num_points = num_points
        self.index = index[0]
        self.var_value = var_value
        self.var_dis = var_dis
        self.var_res = var_res
        'for plot ----------------------------'
        self.region_info = region_info
        'for plot ----------------------------'
        self.split_var = None
        self.split_val = None
        self.split_lab = None
        'for plot ----------------------------'
        self.split_info = None
        'for plot ----------------------------'
        self.left = None
        self.right = None

    def lookup(self, x):
        """Returns the predicting beta parameter.
           here we require that x is a tuple"""
        if self.left == None:
            # Attention! include all continuous vars in regression
            x = numpy.mat(x[self.var_value])
            # y = beta_0 +x*beta
            predict_value = self.predict[0,0] + (x * self.predict[1:,0])[0,0]
            return predict_value
        if isinstance(self.split_val,float) or isinstance(self.split_val,int):
            if x.loc[self.split_var] <= self.split_val:
                return self.left.lookup(x)
            else:
                return self.right.lookup(x)
        else:
            if x.loc[self.split_var] in self.split_val[0]:
                return self.left.lookup(x)
            else:
                return self.right.lookup(x)

    def lookup_sig2(self, x):
        """Returns the standard error"""
        if self.left == None:
            # Attention! include all continuous vars in regression
            return (self.stdev)
        if isinstance(self.split_val,float) or isinstance(self.split_val,int):
            if x.loc[self.split_var] <= self.split_val:
                return self.left.lookup_sig2(x)
            else:
                return self.right.lookup_sig2(x)
        else:
            if x.loc[self.split_var] in self.split_val[0]:
                return self.left.lookup_sig2(x)
            else:
                return self.right.lookup_sig2(x)

    def sig_all(self, data):
        return data.apply(lambda x:self.lookup_sig2(x), axis = 1)


    def predict_all(self, data):
        """Returns the predicted values for a dataframe, and returns a series."""
        return data.apply(lambda x:self.lookup(x), axis = 1)


    def find_weakest(self):
        """Finds the smallest value of alpha and
        the first branch for which the full tree
        does not minimize the error-complexity measure."""
        if (self.right == None):
            return float("Inf"), [self]
        b_error, num_nodes = self.get_cost_params()
        alpha = (self.error - b_error) / (num_nodes - 1)
        alpha_right, tree_right = self.right.find_weakest()
        alpha_left, tree_left = self.left.find_weakest()
        smallest_alpha = min(alpha, alpha_right, alpha_left)
        smallest_trees = []
        # if there are multiple weakest links collapse all of them
        if smallest_alpha == alpha:
            smallest_trees.append(self)
        if smallest_alpha == alpha_right:
            smallest_trees = smallest_trees + tree_right
        if smallest_alpha == alpha_left:
            smallest_trees = smallest_trees + tree_left
        return smallest_alpha, smallest_trees


    def prune_tree(self):
        """Finds {a1, ..., ak} and {T1, ..., Tk},
        the sequence of nested subtrees from which to
        choose the right sized tree."""
        trees = [copy.deepcopy(self)]
        alphas = [0]
        new_tree = copy.deepcopy(self)
        while 1:
            alpha, nodes = new_tree.find_weakest()
            # numerically approximation error
            if alpha < 0:
                alpha = 0
            'for debug ----------------------------'
            #for node in nodes:
            #    print 'the node to be pruned is:', node.index
            'for debug ----------------------------'
            for node in nodes:
                node.right = None
                node.left = None
            trees.append(copy.deepcopy(new_tree))
            alphas.append(alpha)
            # root node reached
            if (node.start == True):
                break
        return alphas, trees


    def get_cost_params(self):
        """Returns the branch error and number of nodes."""
        if self.right == None:
            return self.error, 1
        error, num_nodes = self.right.get_cost_params()
        left_error, left_num = self.left.get_cost_params()
        error += left_error
        num_nodes += left_num
        return error, num_nodes


    def get_length(self):
        """Returns the length of the tree, which means the longest path."""
        if self.right == None:
            return 1
        right_len = self.right.get_length()
        left_len = self.left.get_length()
        return max(right_len, left_len) + 1

    def get_leaf_number(self):
        """Return the number of leaf nodes of the tree."""
        if self.right == None:
            return 1
        else:
            return self.left.get_leaf_number()+self.right.get_leaf_number()

# !!! before invoking grow_tree, a global variable: kendall_tau_total should be defined
#kendall_tau_total = {}
def grow_tree(data, id_value_all, id_cand_all, id_dis, id_res, index, labels = [], depth = 1, \
              max_depth = 500, Nmin = 50,  start = False, feat_bag = False,\
              Nsplit = 100, sNsplit = 5, region_info = 'All Data', mi=0.5):
    """Function to grow a regression tree given some training data."""
    """parameters of Tree: error, predict, stdev, start, num_points, index. """
    """Nsplit is to be passed in get_split_val; sNsplit is to be passed in get_split_var"""
    """id_** means the position of ** names in labels """
    'for debug ----------------------------'
    #print index
    #print 'number of points is,', len(data)
    #print 'Nmin is', Nmin
    'for debug ----------------------------'
    # 0: [for random forest] if  feat_bag=True, choose p^{mi} variables, p:var. dim.
    # mi: tunning parameter; otherwise select all variables.
    num_splitvars = len(id_cand_all)
    num_vars = len(id_value_all)
    if (feat_bag):
        index_bag_cand = random.sample(range(num_splitvars), int(num_splitvars**(mi)))
        index_bag_value = random.sample(range(num_vars), int(num_vars**(mi)))
    else:
        index_bag_cand = range(num_splitvars)
        index_bag_value = range(num_vars)
    id_cand = list(numpy.array(id_cand_all)[index_bag_cand])
    id_value = list(numpy.array(id_value_all)[index_bag_value])
    var_value = labels[id_value]
    if len(id_dis)>0:
        var_dis = labels[id_dis]
    else:
        var_dis = numpy.array([])
    var_res = labels[id_res]
    # sample size should be at least larger than numvars+1
    if(Nmin < 2*(num_vars+1)):
        Nmin = 2*(num_vars+1)
    # get the information of linear regression on region: data
    error, predict, std, y_fit, residual = region_reg_res(data, var_value, var_res)
    root = Tree(error = error, predict = predict, stdev = std,\
                start = start, num_points = len(data), \
                var_value = var_value, var_dis = var_dis,var_res = var_res,\
                index = index, region_info = region_info)
    # regions has fewer than Nmin data points
    if (len(data) <= Nmin):
        'for debug ----------------------------'
        #print 'This is the leaf end and the standard error is', std
        'for debug ----------------------------'
        return root
    # length of tree exceeds max_depth
    if depth >= max_depth:
        'for debug ----------------------------'
        #print 'This is the leaf end and the standard error is', std
        'for debug ----------------------------'
        return root
    # 1: select the split var and select the split point
    split_var,split_val = get_split_var(data, id_cand, id_value, id_dis, labels, residual, Nmin = Nmin, sNsplit = sNsplit)
    'debug 0911---------------------------'
    #print 'split_var is', split_var
    'debug 0911---------------------------'
    if split_val == None:
        'debug 1208---------------------------'
        #print 'split_val is null'
        'debug 1208---------------------------'
        return root
    # 3: pass the information to root node
    root.split_var = split_var
    root.split_val = split_val
    root.split_lab = split_var
    root.index = index[0]
    'for plot ----------------------------'
    'debug 1208---------------------------'
    #print 'split_var is'+split_var+'split_val is'+str(split_val)
    'debug 1208---------------------------'
    if split_var not in var_dis:
        root.split_info = root.split_lab + ': ' + str(float('%.2f' % split_val))
    else:
        root.split_info = root.split_lab + ': ' + str(split_val)
    'for plot ----------------------------'
    # 4: split dataset according to split_var&split_val
    if split_var in var_dis:
        id1 = data[split_var].isin(split_val [0])
        data1 = data.loc[id1].copy()
        id2= data[split_var].isin(split_val [1])
        data2 = data.loc[id2].copy()
    else:
        id1 = data[split_var] <= split_val
        data1 = data.loc[id1].copy()
        id2 = data[split_var] > split_val
        data2 = data.loc[id2].copy()
    'for debug ----------------------------'
    #print 'data1 has ', len(data1.values()), 'rows'
    #print 'data2 has ', len(data2.values()), 'rows'
    'for debug ----------------------------'
    # 5: grow right and left branches
    # index plus one after each growing
    index[0] = index[0]+1
    'for plot ----------------------------'
    if split_var not in var_dis:
        region_info_left = root.split_lab + '<' + str(round(split_val,2))
    else:
        set_str = set2str(split_val[0])
        region_info_left = root.split_lab + ' in ' + set_str
    'for plot ----------------------------'
    root.left = grow_tree(data1, id_value_all, id_cand_all, id_dis, id_res, index, labels = labels,\
                          depth = depth + 1, max_depth = max_depth, Nmin = Nmin, \
                           Nsplit = Nsplit, sNsplit = sNsplit, feat_bag = feat_bag, region_info = region_info_left,mi = mi)
    index[0] = index[0]+1
    'for plot ----------------------------'
    if split_var not in var_dis:
        region_info_right = root.split_lab + '>' + str(round(split_val,2))
    else:
        set_str = set2str(split_val[1])
        region_info_right = root.split_lab + ' in ' + set_str
    'for plot ----------------------------'
    root.right = grow_tree(data2, id_value_all, id_cand_all, id_dis, id_res, index, labels = labels,\
                          depth = depth + 1, max_depth = max_depth, Nmin = Nmin, \
                           Nsplit = Nsplit, sNsplit = sNsplit, feat_bag = feat_bag, region_info = region_info_right,mi=mi)
    return root

def cvt(data, id_value_all, id_cand_all, id_dis, id_res, v, labels = [], max_depth = 500, Nmin = 50, Nsplit = 10, sNsplit = 5, mi=0.5, beta=0):
    """Grows regression tree using v-fold cross validation.

    Data is a dictionary with elements of the form
    (x1, ..., xd) : y where x1, ..., xd are the parameter values and
     y is the response value.
     v is the number of folds for cross validation.
     max_depth is the maximum length of a branch emanating from the starting node.
     Nmin is the number of datapoints that must be present in a region to stop further partitions
     in that region.
     labels is a dictionary where the keys are the indices for the parameters in the data
     and the values are strings assigning a label to the parameters.
     See football_parserf.py for an example implementation."""
    full_tree = grow_tree(data, id_value_all, id_cand_all, id_dis, id_res, [1], labels = labels, \
                          start = True, Nmin = Nmin, Nsplit = Nsplit, sNsplit = sNsplit,mi=mi )
    full_a, full_t = full_tree.prune_tree()
    var_res = labels[id_res].tolist()
    # ak' = (ak * ak+1)^(1/2)
    a_s = []
    for i in range(len(full_a) - 1):
        a_s.append((full_a[i] * full_a[i+1])**(.5))
    a_s.append(full_a[-1])
    #print a_s
    # stratify data, sort data by the rank of y
    # data.sort_values('d_PM2.5',inplace = True)
    # break the data into v subsamples of roughly equal size,
    # [i::v] means start from i and take a step of v to get items
    # lv_s is a list of length v, each element is a dictionary (a subsumple)
    lv_s = [range(i, len(data), v) for i in range(v)]
    # list of tree sequences for each training set
    t_vs = []
    # list of testing data for each training set
    test_vs = []
    # list of alpha values for each training set
    alpha_vs = []

    # grow and prune each training set
    for i in range(len(lv_s)):
        if i==0:
            train_id = reduce(lambda x,y:x+y,lv_s[i+1:])
        elif i==(len(lv_s)-1):
            train_id = reduce(lambda x,y:x+y,lv_s[0:i])
        else:
            train_id = reduce(lambda x,y:x+y,lv_s[0:i])+reduce(lambda x,y:x+y,lv_s[i+1:])
        test_id = lv_s[i]
        train = data.iloc[train_id, ]
        test = data.iloc[test_id, ]
        full_tree_v = grow_tree(train, id_value_all, id_cand_all, id_dis, id_res, [1], labels = labels, \
                                max_depth = max_depth, Nmin = Nmin, sNsplit = sNsplit, start = True,mi=mi)
        alphas_v, trees_v = full_tree_v.prune_tree()
        '------------------check-------------------------'
        t_vs.append(trees_v)
        alpha_vs.append(alphas_v)
        test_vs.append(test)


    # choose the subtree that has the minimum cross-validated
    # error estimate
    min_R = float("Inf")
    # 此处不设为 inf 是因为 0*inf=nan 而任何数字<nan 都为False 其实无论 min_err等于几 第一次 iteration 都会被 replace
    min_err = 1000
    min_ind = 0
    # the length of pruned full_tree
    for i in range(len(full_t)):
        ak = a_s[i]
        R_k = []
        # number of cross validation folds
        for j in range(len(t_vs)):
            # closest alpha value in sequence v to
            # alphak
            a_vs = alpha_vs[j]
            tr_vs = t_vs[j]
            # find the largest one that <= ak in a_vs
            alph_ind = bisect_right(a_vs, ak) - 1
            test_data = test_vs[j]
            pred_vals = tr_vs[alph_ind].predict_all(test_data)
            true_vals = (test_data[var_res]).iloc[:,0]
            r_kv = numpy.mean((numpy.array(true_vals) - numpy.array(pred_vals))**2)
            #print r_kv
            R_k.append(r_kv)
        R_k_mean=numpy.mean(R_k)
        R_k_error=math.sqrt(numpy.var(R_k))
        'for debug 1208----------------------------'
        print i,'th', 'alpha is',ak, 'error is ',R_k_mean
        'for debug 1208----------------------------'
        if (R_k_mean <= min_R+beta*min_err):
            min_R = R_k_mean
            min_err = R_k_error
            min_ind = i
    'for debug 1208----------------------------'
    print min_ind
    'for debug 1208----------------------------'
    return full_t[min_ind]




"""below are the main function for choosing the split_var and split_val"""
def get_split_var(data, id_cand, id_value, id_dis, labels, residual, Nmin ,sNsplit):
    # data is a dataframe iterate over all variables
    # 1. get kendall taus for all candidate split variables
    # 1.0 get data prepared
    data.loc[:,'residual'] = residual
    # 1.1 get candidate split values
    var_split = labels[id_cand]
    if len(id_dis)>0:
        var_dis = labels[id_dis]
    else:
        var_dis = numpy.array([])
    best_split_variable=None
    best_split_value=None
    # attention!in this step,  [20190112]
    # for continuous split variable, we limit the split start from Nmin to len-Nmin
    # for discrete ones, no restrictions here,
    # but will exclude the condition for less than p+1 in kendall's tau cal. step
    split_dict = get_split_dict(var_split, var_dis, data, sNsplit, Nmin)
    # select the var_split that has candidate splits
    var_split_real=[]
    for var in split_dict:
        if(len(split_dict[var])>0):
            var_split_real.append(var)
    var_split_real=numpy.array(var_split_real)
    # if there are exactly no proper splits/that satisfy the sample size restriction, return
    if len(var_split_real)==0:
        return best_split_variable, best_split_value
    # 1.2 get kendall_tau_total prepared
    var_value = labels[id_value]
    kendall_tau_total = {}
    for var in var_split_real:
        kendall_tau_total.update({var: {}})
    '----different from v1--------'
    for split_var in var_split_real:
        for split_val_id in range(len(split_dict[split_var])):
            split_val=(split_dict[split_var])[split_val_id ]
            taus_split=kendall_thread(split_var, split_val, var_dis, var_value, data, Nmin)
            kendall_tau_total[split_var].update({split_val_id:taus_split})
    # 2. cal the criterion and choose the best split value
    # criterion1: the sum of the absolute values of kendall's taus
    criterion1 = {}
    # best_split: the best_split for each candidate split variable
    best_split={}
    for i in kendall_tau_total:
        criterion1[i], best_split[i]= criterion(kendall_tau_total[i],split_dict[i])
    '----different from v1--------'
    # 3. select id_split_best
    best_split_variable =  max(criterion1, key = criterion1.get)
    best_split_value = best_split[best_split_variable]
    if criterion1[best_split_variable]==float('-inf'):
        best_split_variable=None
        best_split_value=None
        return best_split_variable, best_split_value
    return best_split_variable, best_split_value

def kendall_thread(split_var, split_val, var_dis, var_value, data, Nmin):
    taus=[]
    if split_var in var_dis:
        id1 = data[split_var].isin(split_val[0])
        data_part1 = data.loc[id1].copy()
        id2 = data[split_var].isin(split_val[1])
        data_part2 = data.loc[id2].copy()
        for var_v in var_value:
            """set a limitation for the leaf number splitted by a discrete variable"""
            if len(data_part1) > max(Nmin,len(var_value)+1) and len(data_part2) > max(Nmin,len(var_value)+1):
                tau1 = abs(scipy.stats.kendalltau(data_part1[var_v],data_part1['residual'])[0])
                tau2 = abs(scipy.stats.kendalltau(data_part2[var_v],data_part2['residual'])[0])
            else:
                tau1 = float('-inf')
                tau2 = float('-inf')
            taus.append(tau1)
            taus.append(tau2)
    else:
        id1 = data[split_var] <= split_val
        data_part1 = data.loc[id1].copy()
        id2 = data[split_var] > split_val
        data_part2 = data.loc[id2].copy()
        for var_v in var_value:
            if len(data_part1) > len(var_value)+1 and len(data_part2) > len(var_value)+1:
               tau1 = abs(scipy.stats.kendalltau(data_part1[var_v],data_part1['residual'])[0])
               tau2 = abs(scipy.stats.kendalltau(data_part2[var_v],data_part2['residual'])[0])
            else:
               tau1 = float('-inf')
               tau2 = float('-inf')
            taus.append(tau1)
            taus.append(tau2)
    return taus

def criterion(taus_dict,split_val):
    taus_sum={}
    for split in taus_dict:
        taus_sum.update({split: numpy.sum(taus_dict[split])})
    optimal = max(taus_sum, key = taus_sum.get)
    # sum is on regression variables; max is on candidate split values
    taus_sum_max = taus_sum.values()[optimal]
    # best split value for split variable i, the iterative item in the last loop
    best_split = split_val[optimal]
    return taus_sum_max, best_split



"""below are functions used to calculate error and kendall tau,
   will be called for figuring out the best split_var and split_val"""

def region_reg_res(data, var_value, var_res):
    """Calculates sum of squared error for some node in the regression tree.
       here data is a dictionary, where the keys corresponde to dependent vars. and
       value correspond to independent variables"""
    nvar = len(var_value)
    nrow = len(data)
    x = numpy.mat(data[var_value])
    y = numpy.mat(data[var_res])
    if y.shape[1]!=1:
        y=y.T
    xx = numpy.c_[numpy.ones(nrow),x]
    #xx_0 = numpy.c_[numpy.ones(nrow),x] # add (1) column to calculate intercept
    #xx = xx_0.astype(numpy.float64)
    xx_inv = numpy.linalg.pinv(xx.T*xx)
    beta = xx_inv*xx.T*y # beta is (p+1)*1, a column vector
    y_fit = (xx*beta) # y_fit is a row vector
    residual = y_fit-y
    sse = (residual.T * residual)[0,0] # sse is a float type
    #print 'sse is', sse , 'nrow-nvar-1 is', nrow-nvar-1
    sigma = math.sqrt(sse/(nrow-nvar-1)) # sigma is a foat type
    residual = numpy.matrix.tolist((y_fit-y).T)[0] # residual is a list
    # change the error for the adaptive definition of I(T) 190505
    return sse, beta, sigma, y_fit, residual


def error_function_con(split_val, split_var, var_value, var_res, data, Nmin):
    """Function calculate the error of one node, given split_point/value.
       split_* is int, data is dictionary."""
    id1 = data[split_var] <= split_val
    data1 = data.loc[id1].copy()
    id2 = data[split_var] > split_val
    data2 = data.loc[id2].copy()
    nrow1 = len(data1)
    nrow2 = len(data2)
    if (nrow1-Nmin) < 0 or (nrow2-Nmin) < 0:
        return -1
    else:
        return region_reg_res(data1, var_value, var_res)[0] + region_reg_res(data2, var_value, var_res)[0]

def error_function_dis(split_val, split_var, var_value, var_res, data, Nmin):
    """Function calculate the error of one node, given split_val/value.
       split_var is discrete variable, data is dictionary."""
    id1 = data[split_var].isin(split_val [0])
    data1 = data.loc[id1].copy()
    id2 = data[split_var].isin(split_val [1])
    data2 = data.loc[id2].copy()
    nrow1 = len(data1)
    nrow2 = len(data2)
    nmin = 2*(len(var_value)+1)
    if (nrow1-Nmin/2) < 0 or (nrow2-Nmin/2) < 0 or (nrow1-nmin/2) < 0 or (nrow2-nmin) < 0:
        return -1
    else:
        return region_reg_res(data1, var_value, var_res)[0] + region_reg_res(data2, var_value, var_res)[0]
"""var_split and var_dis are both numpy.array"""
def get_split_dict(var_split, var_dis, data, sNsplit, Nmin):
    """function to return a dictionary of candidate splits
        where the keys are split variables and the corres. values are split points"""
    split_dict = {}
    for var in var_split:
        if var not in var_dis:
            x_split_list = data[var].values
            x_split_ranked = numpy.sort(x_split_list)
            id_str = Nmin
            id_end = len(x_split_list)-Nmin
            id_mid = numpy.arange(id_str, id_end, 1)
            x_split_unique = list(set(x_split_ranked[id_mid]))
            """mostly for ordered categorical variable"""
            if(len(x_split_unique)<sNsplit):
                split_range = x_split_unique
            else:
                #step = max(100/(sNsplit+1), 100*(Nmin/2)/len(data))
                step = len(id_mid)/sNsplit
                if step == 0:
                    step = 1
                id_split = numpy.arange(id_str, id_end, step)
                split_range = x_split_ranked[id_split]
            split_dict.update({var:split_range})
        else:
            x_split_set = list(set(data[var].values))
            split_range_all = list(paired_power_set(x_split_set))
            if len(split_range_all)>2*sNsplit:
                split_range = random.sample(split_range_all, 2*sNsplit)
            else:
                split_range = split_range_all
            split_dict.update({var:split_range})
    return split_dict
"""get kendall tau, suitable for runing in threadings"""
def sig_number(l):
    l = numpy.array(l)
    """Function to tell if significant taus exist, here l is a list"""
    l1 = l[0::2]
    l2 = l[1::2]
    sig_pair = (l1<0.05)&(l2<0.05)
    sig_num = numpy.sum(sig_pair)
    if sig_num>0:
        return sig_num
    else:
        return 0

def sig_mean(l):
    l = numpy.array(l)
    """Function to calculate the mean of significant taus, here l is a list
       if there are no significant ones, return 1"""
    l1 = l[0::2]
    l2 = l[1::2]
    sig_pair = (l1<0.05)&(l2<0.05)
    if numpy.sum(sig_pair)>0:
        return (numpy.mean(l1[sig_pair])+numpy.mean(l2[sig_pair]))/2
    else:
        return 1
def sig_mean_total(l):
    l = numpy.array(l)
    if len(l[l<0.05])>0:
        res = numpy.mean(l[l<0.05])
    else:
        res = 1
    return numpy.mean(res)

def paired_power_set(s):
    """This function returns an iterator, each value is a pair of sets"""
    """they are complementary, either is complete or empty"""
    n = len(s)
    test_marks = [1<<i for i in range(0,n)] # <<i 相当于 *2^{i}
    pair_1 = range(1, 2**n-1)[0::2]
    pair_2 = range(1, 2**n-1)[1::2]
    pair_2.reverse()
    pair = zip(pair_1, pair_2)
    for k1, k2 in pair:
        l1 = []
        l2 = []
        for idx, item in enumerate(test_marks): # enumerate returns a iterator
            if k1&item:
                l1.append(s[idx])
            if k2&item:
                l2.append(s[idx])
        yield [set(l1),set(l2)]
def set2str(set):
    if len(set)==1:
        return '{ '+str(list(set)[0])+' }'
    else:
        return '{ '+reduce(lambda x,y: str(x)+', '+str(y), set)+' }'

"""below are functions to get information from growned trees"""
def get_splits(tree, dic):
    if tree.left!=None and tree.right!=None:
        var_node=tree.split_var
        value_node=tree.split_val
        dic[var_node].append(value_node)
        dic= get_splits(tree.left, dic)
        dic= get_splits(tree.right, dic)
        return dic
    else:
        return dic
def get_path(tree, li, path):
    """Get a list of all paths, where each element is one single path
    corresponding to a node.
    when call the function, the parameters shoulde be [] and [], for eg,
    res = get_paths(tree,[],[])."""

    if tree.right != None:
        if isinstance(tree.split_val, float) or isinstance(tree.split_val,int):
            li.append(tree.split_lab+'<'+str(tree.split_val))
            path=get_path(tree.left, li, path)
            li.pop()
            li.append(tree.split_lab+'>'+str(tree.split_val))
            path=get_path(tree.right, li, path)
            li.pop()
            return path
        else:
            li.append(tree.split_lab+' in '+str(tree.split_val[0]))
            path=get_path(tree.left, li, path)
            li.pop()
            li.append(tree.split_lab+' in '+str(tree.split_val[1]))
            path=get_path(tree.right, li, path)
            li.pop()
            return path
    else :
        path.append(copy.deepcopy(li))
        return path

# get the index set of all terminal/leaf nodes
def get_leaf_index(tree, leaves):
    """Get the index of all leaves. when function is called, leaves should be
        set as [],see: get_leaf_index(tree, [])"""
    if tree.right != None:
        leaves = get_leaf_index(tree.left, leaves)
        leaves = get_leaf_index(tree.right, leaves)
        return leaves
    else:
        leaves.append(tree.index)
        return leaves

# get a dictionary of predictive parameters beta all terminal/leaf nodes
def get_leaf_beta(tree, betas):
    """key: leaf index ; value: beta
        the order is the same as leaves"""
    if tree.right != None:
        betas = get_leaf_beta(tree.left, betas)
        betas = get_leaf_beta(tree.right, betas)
        return betas
    else:
        betas.update({tree.index: tree.predict})
        return betas

# get a dictionary of sigma (sigma = sse/(n-p-1)) over all terminal/leaf nodes
def get_leaf_sigma(tree, sigma):
    """key: leaf index ; value: sigma
        the order is the same as leaves"""
    if tree.right != None:
        sigma = get_leaf_sigma(tree.left, sigma)
        sigma = get_leaf_sigma(tree.right, sigma)
        return sigma
    else:
        sigma.update({tree.index: tree.stdev})
        return sigma

# return the leaf node where each of the record belong to
def get_matching_node(tree, x):
    """Return the index of the leaf node which the record x belongs to"""
    if tree.right != None:
#        print tree.split_val
#        print tree.index
        if isinstance(tree.split_val, float) or isinstance(tree.split_val,int):
            if x[tree.split_var] <= tree.split_val:
                return get_matching_node(tree.left, x)
            else:
                return get_matching_node(tree.right, x)
        else:
            if x[tree.split_var] in tree.split_val[0]:
                return get_matching_node(tree.left, x)
            else:
                return get_matching_node(tree.right, x)
    else:
        return tree.index

# partition the data in to all "leaves"
def data_partition(tree, data):
    """Return a large dictionary, where the keys are the index of leaves and
       for a certain leaf, the corresponding value is the sub-dictionary this leaf"""
    leaf_list = get_leaf_index(tree,[])
    #data_leaf_index = numpy.array([get_matching_node(tree,i) for i in data.keys()])
    data.loc[:,'leaf']=data.apply(lambda x:get_matching_node(tree, x), axis = 1)
    data_partition = {}
    for l in range(len(leaf_list)):
        data_partition[leaf_list[l]] = data[data['leaf']==leaf_list[l]].copy()
    return data_partition
