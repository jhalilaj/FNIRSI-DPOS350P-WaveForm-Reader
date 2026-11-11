"""Scope-style static renderer; controls are labels, not simulated measurements."""
def render(channels, filename, destination):
    samples = [value for values in channels.values() for value in values]
    count = max(map(len, channels.values()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import MultipleLocator
    fig = plt.figure(figsize=(12.8, 7.5), facecolor='#16191d')
    ui = fig.add_axes([0, 0, 1, 1]); ui.set_axis_off()
    def text(x, y, value, color='#dfe4e8', size=10, **kw):
        ui.text(x, y, value, color=color, fontsize=size, transform=ui.transAxes, **kw)
    def box(x,y,w,h,label,color='#dfe4e8'):
        ui.add_patch(Rectangle((x,y),w,h,facecolor='#292e35',edgecolor='#444a52',lw=.7))
        text(x+w/2,y+h/2,label,color,9,ha='center',va='center')
    text(.024,.959,'FNIRSI',size=19,weight='bold')
    text(.135,.962,'DPOS350P  /  WAVEFORM REPLAY',size=10,color='#98a6b2')
    text(.975,.962,'OFFLINE',color='#ffcc42',ha='right',weight='bold')
    for i,label in enumerate(['System','Measure','Browser','Cursor X','Cursor Y','Save wave','Screenshot','Zoom']):
        box(.022+i*.12,.884,.112,.052,label)
    text(.028,.85,filename,color='#ffd735',size=11)
    text(.51,.85,f'{count:,} samples / channel',size=10)
    text(.956,.85,'RAW  /  UNCALIBRATED',color='#92a1ad',ha='right',size=10)
    ax = fig.add_axes([.045,.245,.805,.58],facecolor='#080a0c')
    lo,hi=min(samples),max(samples); span=max(hi-lo,1); bottom=lo-span*.12; top=hi+span*.12
    ax.set_xlim(0,count-1); ax.set_ylim(bottom,top)
    ax.xaxis.set_major_locator(MultipleLocator((count-1)/12))
    ax.yaxis.set_major_locator(MultipleLocator((top-bottom)/8))
    ax.xaxis.set_minor_locator(MultipleLocator((count-1)/60))
    ax.yaxis.set_minor_locator(MultipleLocator((top-bottom)/40))
    ax.grid(which='major',color='#343a40',lw=.65)
    ax.grid(which='minor',color='#20252a',lw=.35,linestyle=':')
    ax.tick_params(which='both',length=0,labelbottom=False,labelleft=False)
    for spine in ax.spines.values(): spine.set_color('#515961')
    ax.axhline((top+bottom)/2,color='#68717a',lw=.55,linestyle='--')
    ax.axvline((count-1)/2,color='#68717a',lw=.55,linestyle='--')
    for (name, values), color in zip(channels.items(), ['#fff05a', '#00e5e5']):
        ax.plot(values,color=color,lw=.65,label=name)
    ax.legend(loc='upper left', facecolor='#080a0c', edgecolor='none', labelcolor='linecolor')
    for i,(label,col) in enumerate([('TRACE','#ffdb32'),('Full record','#dfe4e8'),('Raw data','#dfe4e8'),('Trigger: --','#98a6b2')]):
        box(.866,.736-i*.105,.112,.075,label,col)
    text(.046,.208,f'RAW MIN  {lo:,}     MAX  {hi:,}     SPAN  {hi-lo:,} counts',color='#ffdb32',size=11)
    for i,(label,col) in enumerate([('CHANNELS   Raw counts','#ffdb32'),('V / div    --','#ffdb32'),('TIME / div    --','#dfe4e8'),('SAMPLE RATE    --','#dfe4e8')]):
        box(.022+i*.244,.115,.233,.063,label,col)
    text(.025,.069,'Experimental decoding  |  Channel assignment, voltage and time calibration pending',color='#9ca8b2',size=10)
    text(.975,.025,'FNIRSI-style replay display',color='#65717c',size=9,ha='right')
    fig.savefig(destination,dpi=160,facecolor=fig.get_facecolor());plt.close(fig)

