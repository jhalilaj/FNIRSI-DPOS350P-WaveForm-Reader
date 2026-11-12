"""Offline measurements. Frequency/duty are threshold estimates, not clock calibration."""
import math,statistics
from bisect import bisect_left,bisect_right


def analyze(values,dt=None):
    if not values:raise ValueError('No samples selected')
    n=len(values);mean=math.fsum(values)/n
    result={'minimum':min(values),'maximum':max(values),'peak_to_peak':max(values)-min(values),
            'mean':mean,'rms':math.sqrt(math.fsum(v*v for v in values)/n),
            'ac_rms':math.sqrt(math.fsum((v-mean)**2 for v in values)/n),
            'frequency_hz':None,'period_s':None,'duty_percent':None,'cycles':0,
            'positive_width_s':None,'negative_width_s':None,'rise_time_s':None,'fall_time_s':None,
            'timing_method':'interpolated threshold estimates; rise/fall 10–90% of robust signal levels; edges shorter than two sample intervals unresolved'}
    if not dt or dt<=0 or n<8:return result
    ordered=sorted(values);lo=ordered[n//10];hi=ordered[9*n//10]
    if hi-lo<=max(1e-12,abs(mean)*1e-6):return result
    result['rise_time_s'],result['fall_time_s']=transition_times(values,dt,lo,hi)
    mid=(hi+lo)/2;lower=lo+.3*(hi-lo);upper=lo+.7*(hi-lo)
    armed=False;edges=[]
    for i,v in enumerate(values):
        if v<lower:armed=True
        elif armed and v>upper:
            j=i
            while j>0 and values[j-1]>mid:j-=1
            if j>0 and values[j]!=values[j-1]:
                edges.append(j-1+(mid-values[j-1])/(values[j]-values[j-1]))
            armed=False
    periods=[b-a for a,b in zip(edges,edges[1:])]
    if not periods:return result
    median=statistics.median(periods)
    if median<4 or (len(periods)>1 and max(abs(p-median)/median for p in periods)>.05):return result
    result.update(frequency_hz=1/(median*dt),period_s=median*dt,cycles=len(periods))
    falls=[]
    for i in range(1,n):
        if values[i-1]>mid>=values[i]:
            falls.append(i-1+(values[i-1]-mid)/(values[i-1]-values[i]))
    high=[];low=[]
    for a,b in zip(edges,edges[1:]):
        first=bisect_right(falls,a);last=bisect_left(falls,b)
        if last-first==1:
            high.append((falls[first]-a)*dt);low.append((b-falls[first])*dt)
    if len(high)==len(periods):
        result['positive_width_s']=statistics.median(high)
        result['negative_width_s']=statistics.median(low)
    start,end=math.ceil(edges[0]),math.ceil(edges[-1])
    if end>start:result['duty_percent']=100*sum(v>=mid for v in values[start:end])/(end-start)
    return result


def transition_times(values,dt,lo,hi):
    """Completed 10–90% transitions; report only durations >= two samples."""
    lower=lo+.1*(hi-lo);upper=lo+.9*(hi-lo)
    rising=[];falling=[];rise_start=None;fall_start=None
    for i in range(1,len(values)):
        a,b=values[i-1],values[i]
        if b>a:
            if a<=lower<b:rise_start=i-1+(lower-a)/(b-a)
            if a<upper<=b:
                if rise_start is not None:
                    duration=(i-1+(upper-a)/(b-a)-rise_start)*dt
                    if duration>=2*dt:rising.append(duration)
                rise_start=None
        elif b<a:
            if b<upper<=a:fall_start=i-1+(a-upper)/(a-b)
            if b<=lower<a:
                if fall_start is not None:
                    duration=(i-1+(a-lower)/(a-b)-fall_start)*dt
                    if duration>=2*dt:falling.append(duration)
                fall_start=None
        if b<lower:rise_start=None
        if b>upper:fall_start=None
    return (statistics.median(rising) if rising else None,statistics.median(falling) if falling else None)
