class measurement:
    method="Derivative" #Default error propogation method
    mcTrials=10000 #option for number of trial in Monte Carlo simulation
    style="Default"
    figs=3
    register={}
    formula_register={}
    
    #Defining common types under single array
    CONSTANT = (int,float,)
    ARRAY = (list,tuple)
    try:
        import numpy
    except ImportError:
        print("Please install numpy for full features.")
        numpy_installed=False
    else:
        ARRAY+=(numpy.ndarray,)
        numpy_installed=True
    
    def __init__(self,*args,name=None):
        '''
        Creates a variable that contains a mean, standard deviation, 
        and name for inputted data.
        '''
        
        if len(args)==2 and all(isinstance(n,measurement.CONSTANT)\
                for n in args):
            self.mean=args[0]
            self.std=args[1]
            data=None
            
        elif all(isinstance(n,measurement.ARRAY) for n in args) and \
                len(args)==1:
            args=args[0]
            (self.mean, self.std) = variance(args)
            #self.std = std(args,ddof=1)
            data=list(args)
        elif len(args)>2:
            (self.mean, self.std) = variance(args)
            #self.std = std(args,ddof=1)
            data=list(args)
        else:
            raise ValueError('''Input arguments must be one of: a mean and 
            standard deviation, an array of values, or the individual values
            themselves.''')
        self.info={'ID': '', 'Formula': '' ,'Method': 'Empty', 'Data': data}
        self.MC_list=None

    def set_method(chosen_method):
        '''
        Choose the method of error propagation to be used. Enter a string.       
        
        Function to change default error propogation method used in 
        measurement functions.
        '''
        mc_list=('MC','mc','montecarlo','Monte Carlo','MonteCarlo',\
                'monte carlo',)
        min_max_list=('Min Max','MinMax','minmax','min max',)
        derr_list=('Derivative', 'derivative','diff','der',)
        default = 'Derivative'        
        
        if chosen_method in mc_list:
            if measurement.numpy_installed:
                measurement.method="Monte Carlo"
            else:
                #print('Numpy package must be installed to use Monte Carlo \
                #        propagation, using the derivative method instead.')
                #measurement.method="Derivative"
                measurement.method="Monte Carlo"
        elif chosen_method in min_max_list:
            measurement.method="Min Max"
        elif chosen_method in derr_list:
            measurement.method="Derivative"
        else:
            print("Method not recognized, using"+default+"method.")
            measurement.method="Derivative"
        
    def __str__(self):
        if measurement.style=="Latex":
            string = tex_print(self)
        elif measurement.style=="Default":
            string = def_print(self)
        elif measurement.style=="SigFigs":
            string = sigfigs_print(self,measurement.figs)
        return string
        
    def print_style(style,figs=3):
        latex=("Latex","latex",'Tex','tex',)
        Sigfigs=("SigFigs","sigfigs",'figs','Figs',\
                "Significant figures","significant figures",)
        if style in latex:
            measurement.style="Latex"
        elif style in Sigfigs:
            measurement.style="SigFigs"
            measurement.figs=figs
        else:
            measurement.style="Default"
            
        
    def find_covariance(x,y):
        '''
        Uses the data from which x and y were generated to calculate
        covariance and add this informaiton to x and y.
        
        Requires data arrays to be stored in the .info of both objects
        and that these arrays are of the same length, as the covariance is
        only defined in these cases.
        '''
        data_x=x.info["Data"]
        data_y=y.info["Data"]
        
        if data_x is None or data_y is None:
            raise TypeError("Data arrays must exist for both quantities " 
            +"to define covariance.")
        #elif len(data_x)==1 or len(data_y)==1:
            
        if len(data_x)!=len(data_y):
            raise TypeError('Lengths of data arrays must be equal to\
                      define a covariance')
        sigma_xy=0
        for i in range(len(data_x)):
              sigma_xy+=(data_x[i]-x.mean)*(data_y[i]-y.mean)
        sigma_xy/=(len(data_x)-1)

        x.covariance['Name'].append(y.name)
        x.covariance['Covariance'].append(sigma_xy)
        y.covariance['Name'].append(x.name)
        y.covariance['Covariance'].append(sigma_xy)

    def set_correlation(self,y,factor):
        '''
        Manually set the correlation between two quantities
        
        Given a correlation factor, the covariance and correlation
        between two variables is added to both objects.
        '''
        x=self
        ro_xy=factor
        sigma_xy=ro_xy*x.std*y.std

        x.covariance['Name'].append(y.name)
        x.covariance['Covariance'].append(sigma_xy)
        y.covariance['Name'].append(x.name)
        y.covariance['Covariance'].append(sigma_xy)

    def get_covariance(self,variable):
        '''
        Returns the covariance of the object and a specified variable.
        
        This funciton checks for the existance of a data array in each 
        object and that the covariance of the two objects is not already
        specified. In each case, the covariance is returned, unless
        the data arrays are of different lengths or do not exist, in that
        case a covariance of zero is returned.        
        '''
        if self.info['Data'] is not None \
                and variable.info['Data'] is not None \
                and all(self.covariance['Name'][i]!=variable.name \
                for i in range(len(self.covariance['Name']))):
            measurement.find_covariance(self,variable)
            
        if any(self.covariance['Name'][i]==variable.name
                   for i in range(len(self.covariance['Name']))):
            for j in range(len(self.covariance["Name"])):
                if self.covariance["Name"][j]==variable.name:
                    index=j
                    return self.covariance["Covariance"][index]
        else:
            return 0;
    
    def get_correlation(x,y):
        '''
        Returns the correlation factor of two measurements.
        
        Using the covariance, or finding the covariance if not defined,
        the correlation factor of two measurements is returned.        
        '''
        if y.name in x.covariance['Name']:
            pass
        else:
            measurement.find_covariance(x,y)
        sigma_xy=x.covariance[y.name]
        sigma_x=x.covariance[x.name]
        sigma_y=y.covariance[y.name]
        return sigma_xy/sigma_x/sigma_y    
        
    def rename(self,newName):
        '''
        Renames an object, requires a string.
        '''
        self.name=newName
    
    def _update_info(self, operation, var1, var2=None, func_flag=None):
        '''
        Update the formula, name and method of an object.        
        
        Function to update the name, formula and method of a value created
        by a measurement operation. The name is updated by combining the 
        names of the object acted on with another name using whatever 
        operation is being performed. The function flag is to change syntax 
        for functions like sine and cosine. Method is updated by acessing 
        the class property.
        '''
        if func_flag is None and var2 is not None:
            self.rename(var1.name+operation+var2.name)
            self.info['Formula']=var1.info['Formula']+operation+\
                    var2.info['Formula']
            measurement.formula_register.update({self.info["Formula"]\
                    :self.info["ID"]})
            self.info['Method']+="Errors propagated by "+measurement.method+\
                    ' method.\n'
            for root in var1.root:
                if root not in self.root:
                    self.root+=var1.root
            for root in var2.root:
                if root not in self.root:
                    self.root+=var2.root
        elif func_flag is not None:
            self.rename(operation+'('+var1.name+')')
            self.info['Formula']=operation+'('+var1.info['Formula']+')'
            self.info['Method']+="Errors propagated by "+measurement.method+\
                    ' method.\n'
            measurement.formula_register.update({self.info["Formula"]\
                    :self.info["ID"]})
            for root in var1.root:
                if root not in self.root:
                    self.root+=var1.root
        else:
            print('Something went wrong in update_info')
            
            
    def d(self,variable=None):
        '''
        Returns the numerical value of the derivative with respect to an 
        inputed variable.        
        
        Function to find the derivative of a measurement or measurement like
        object. By default, derivative is with respect to itself, which will
        always yeild 1. Operator acts by acessing the self.first_der 
        dictionary and returning the value stored there under the specific
        variable inputted (ie. deriving with respect to variable=???)
        '''
        if variable is not None \
                and not hasattr(variable,'type'):
            return 'Only measurement objects can be derived.'
        elif variable is None:
            return self.first_der
        if variable.info['ID'] not in self.first_der:
            self.first_der[variable.info['ID']]=0
        derivative=self.first_der[variable.info["ID"]]
        return derivative
    
    def check_der(self,b):
        '''
        Checks for a derivative with respect to b, else zero is defined as
        the derivative.        
        
        Checks the existance of the derivative of an object in the 
        dictionary of said object with respect to another variable, given
        the variable itself, then checking for the ID of said variable
        in the .first_der dictionary. If non exists, the deriviative is 
        assumed to be zero.
        '''
        for key in b.first_der:
            if key in self.first_der:
                pass;
            else:
                self.first_der[key]=0

#######################################################################
#Operations on measurement objects
    
    def __add__(self,other):
        from operations import add
        return add(self,other)
    def __radd__(self,other):
        from operations import add
        return add(self,other);  

    def __mul__(self,other):
        from operations import mul
        return mul(self,other);
    def __rmul__(self,other):
        from operations import mul
        return mul(self,other);
        
    def __sub__(self,other):
        from operations import sub
        return sub(self,other);
    def __rsub__(self,other):
        from operations import sub
        result=sub(other,self)
        #result._update_info('-',other,self)
        return result
        
    def __truediv__(self,other):
        from operations import div
        return div(self,other);
    def __rtruediv__(self,other):
        from operations import div
        return div(other,self);
        
    def __pow__(self,other):
        from operations import power
        return power(self,other)
    def __rpow__(self,other):
        from operations import power
        return power(other,self)
        
    def __neg__(self):
        if self.type=="Constant":
            return constant(-self.mean,self.std,name='-'+self.name)
        else:
            return function(-self.mean,self.std,name='-'+self.name)

#######################################################################
    
    def monte_carlo(func,*args):
        '''
        Uses a Monte Carlo simulation to determine the mean and standard 
        deviation of a function.
        
        Inputted arguments must be measurement type. Constants can be used
        as 'normalized' quantities which produce a constant row in the 
        matrix of normally randomized values.
        '''
        #2D array
        import numpy as np
        N=len(args)
        n=measurement.mcTrials #Can be adjusted in measurement.mcTrials
        value=np.zeros((N,n))
        result=np.zeros(n)
        for i in range(N):
            if args[i].MC_list is not None:
                value[i]=args[i].MC_list
            elif args[i].std==0:
                value[i]=args[i].mean
                args[i].MC_list=value[i]
            else:
                value[i]=np.random.normal(args[i].mean,args[i].std,n)
                args[i].MC_list=value[i]
                
        result=func(*value)
        data=np.mean(result)
        error=np.std(result,ddof=1)
        argName=""
        for i in range(N):
            argName+=','+args[i].name
        name=func.__name__+"("+argName+")"
        return function(data,error,name=name)
        
class function(measurement):
    id_number=0    
    
    def __init__(self,*args,name=None):    
        super().__init__(*args)
        if name is not None:
            self.name=name
        else:
            self.name='obj%d'%(function.id_number)
        self.info['ID']='obj%d'%(function.id_number)
        self.type="function"
        function.id_number+=1
        self.first_der={self.info['ID']:1}
        measurement.register.update({self.info["ID"]:self})
        self.covariance={'Name': [self.name], 'Covariance': [self.std**2]}
        self.root=()
            
class measured(measurement):
    id_number=0    
    
    def __init__(self,*args,name=None):
        super().__init__(*args)
        if name is not None:
            self.name=name
        else:
            self.name='var%d'%(measured.id_number)
        self.type="measurement"
        self.info['ID']='var%d'%(measured.id_number)
        self.info['Formula']='var%d'%(measured.id_number)
        measured.id_number+=1
        self.first_der={self.info['ID']:1}
        self.covariance={'Name': [self.name], 'Covariance': [self.std**2]}
        measurement.register.update({self.info["ID"]:self})
        self.root=(self.info["ID"] ,)

class constant(measurement):
    def __init__(self,arg,name=None):
        super().__init__(arg,0)
        if name is not None:
            self.name=name
        else:
            self.name='%d'%(arg)
        self.info['ID']='Constant'
        self.info["Formula"]='%d'%arg
        self.first_der={self.info['ID']:0}
        self.info["Data"]=[arg]
        self.type="Constant"
        self.covariance={'Name': [self.name], 'Covariance': [0]}
        self.root=()
   
def f(function,*args):
    N=len(args)
    mean=function(args)
    std_squared=0
    for i in range(N):
        for arg in args:        
            std_squared+=arg.std**2*partial_derivative(function,i,args)**2
    std=(std_squared)**(1/2)
    argName=""
    for i in range(N):
        argName+=','+args[i].name
    name=function.__name__+"("+argName+")"
    return measurement(mean,std,name=name);
      
def partial_derivative(func,var,*args):
    '''
    Returns the parital derivative of a dunction with respect to var.
    
    This function wraps the inputted function to become a function
    of only one variable, the derivative is taken with respect to said
    variable.
    '''    
    def restrict_dimension(x):
        partial_args=list(args)
        partial_args[var]=x
        return func(*partial_args);
    return derivative(restrict_dimension,args[var])

def derivative(function,point,dx=1e-10):
    '''
    Returns the first order derivative of a function.
    '''
    return (function(point+dx)-function(point))/dx
    
def variance(*args,ddof=1):
    '''
    Returns a tuple of the mean and standard deviation of a data array.
    
    Uses a more sophisticated variance calculation to speed up calculation of
    mean and standard deviation.
    '''
    args=args[0]
    Sum=0
    SumSq=0
    N=len(args)
    mean=sum(args)/len(args)
    for i in range(N):
        Sum+=args[i]
        SumSq+=args[i]*args[i]        
    std=((SumSq-Sum**2/N)/(N-1))**(1/2)
    return (mean,std);
    
def tex_print(self):
    flag=True
    i=0
    value=self.std
    while(flag):
        if value==0:
            std=int(self.std/10**i//1)
            mean=int(self.mean/10**i//1)
            return "(%d \pm %d)\e%d"%(mean,std,i)
        if value<1:
            value*=10
            i-=1
        elif value>10:
            value/=10
            i+=1
        elif value>=1 and value<=10:
            flag=False
    std=int(self.std/10**i//1)
    mean=int(self.mean/10**i//1)
    return "(%d \pm %d)\e%d"%(mean,std,i)
    
def def_print(self):
    flag=True
    i=0
    value=self.std
    while(flag):
        if value==0:
            flag=False
        elif value<1:
            value*=10
            i+=1
        elif value>10:
            value/=10
            i-=1
        elif value>=1 and value<=10:
            flag=False
    if i>0:
        n='%d'%(i)
        n="%."+n+"f"
    else:
        n='%.0f'
    std=float(round(self.std,i))
    mean=float(round(self.mean,i))
    return n%(mean)+" +/- "+n%(std)

def sigfigs_print(self,figs):
    n=figs-1
    n='{:.'+'%d'%(n)+'e}'
    return n.format(self.mean)+'+/-'+n.format(self.std)