"""Cursor statistics: X selects time samples; Y selects an amplitude band."""
import math

def stats(values):
    if not values:return {'count':0,'minimum':None,'maximum':None,'mean':None}
    return {'count':len(values),'minimum':min(values),'maximum':max(values),'mean':math.fsum(values)/len(values)}

def x_selection(values,a,b,dt=None):
    if not values:
        return dict(stats(values),delta_s=None,one_cycle_hz=None)
    a=max(0,min(len(values)-1,int(a)));b=max(0,min(len(values)-1,int(b)))
    lo,hi=sorted((a,b));result=stats(values[lo:hi+1])
    delta=(b-a)*dt if dt and dt>0 else None
    result.update(delta_s=delta,one_cycle_hz=1/abs(delta) if delta else None)
    return result

def y_selection(values,a,b):
    low,high=sorted((a,b))
    return stats([v for v in values if low<=v<=high])
