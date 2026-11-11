"""Repeatable checks against the seven user-supplied reference captures."""
from pathlib import Path
import argparse,csv,json,statistics
from fnirsi_decode import decode,channel_samples
from calibration import volts


def square_measurements(values,dt):
    ordered=sorted(values);n=len(ordered)
    lo,hi=ordered[n//10],ordered[9*n//10]
    midpoint=(lo+hi)/2
    low=statistics.median(v for v in values if v<midpoint)
    high=statistics.median(v for v in values if v>=midpoint)
    # Hysteresis prevents multiple edge detections from transition ringing.
    arm=False;edges=[];lower=lo+.3*(hi-lo);upper=lo+.7*(hi-lo)
    for i,value in enumerate(values):
        if value<lower:arm=True
        elif arm and value>upper:edges.append(i);arm=False
    periods=[b-a for a,b in zip(edges,edges[1:])]
    return {'low_v':low,'high_v':high,'plateau_vpp':high-low,'plateau_offset_v':(low+high)/2,
            'frequency_hz':1/(statistics.median(periods)*dt) if periods else None,
            'periods_used':len(periods)}


def validate(source,output):
    output.mkdir(parents=True,exist_ok=True);rows=[]
    for number in range(1,8):
        path=source/f'{number}.wav';meta,raw=decode(path.read_bytes())
        channels=volts(meta,channel_samples(meta,raw));dt=meta['calibration']['sample_interval_s_candidate']
        dest=output/str(number);dest.mkdir(exist_ok=True)
        (dest/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
        with (dest/'voltage-time.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f);writer.writerow(['sample_index','relative_time_s',*[k+'_volts_model' for k in channels]])
            writer.writerows((i,i*dt,*row) for i,row in enumerate(zip(*channels.values())))
        for name,values in channels.items():
            row={'pair':number,'channel':name,'mean_v':statistics.mean(values),'samples':len(values)}
            if number>=3:
                row.update(square_measurements(values,dt))
                assert abs(row['frequency_hz']-1000)<1,(number,name,'timing')
                assert abs(row['plateau_vpp']-5)<.15,(number,name,'amplitude')
                assert abs(row['plateau_offset_v']-.5)<.02,(number,name,'offset')
            if number==1:assert abs(row['mean_v'])<.01
            if number==2:assert abs(row['mean_v']-4.87)<.03 # scope readout, not nominal supply label
            rows.append(row)
    (output/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    lines=['# Reference-capture validation','','Checks passed for all seven supplied pairs. These validate the model for the supplied 1X captures; they are not a traceable hardware calibration.','',
           '| Pair | Channel | Mean V | Plateau Vpp | Plateau offset V | Frequency Hz | Periods used |',
           '|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        fmt=lambda key: f'{r[key]:.6f}' if key in r else '-'
        lines.append(f"| {r['pair']} | {r['channel']} | {r['mean_v']:.6f} | {fmt('plateau_vpp')} | {fmt('plateau_offset_v')} | {fmt('frequency_hz')} | {r.get('periods_used','-')} |")
    lines+=['','Timing correction: interval = retained_seconds_per_div / (95 * samples_per_pixel). The previous divisor 100 caused a 5.26% frequency error. Both timebases and both channel layouts now agree with the declared 1 kHz source to within 1 Hz. This is a regression acceptance bound, not an accuracy specification.','',
            'The DC source labeled 5 V decodes to about 4.868 V, consistent with the scope reading around 4.87 V; its actual output was not independently measured here.','',
            'Pair 7 verifies CH2 zero-position compensation: moving its displayed trace does not produce a comparable shift in decoded physical voltage. CH2-only packing is now exercised by pair 6.','',
            'Screenshots show acquisition running. Pair extrema and stored readouts can describe different frames, so exact equality is not required. Plateaus and frequency provide the main known-signal checks. Pair 4 shows 2 V/div, not 25 V/div; pair 5 shows 200 us/div. The WAV retained scales also change, so these are not an isolated test of edits to one held acquisition. The old 14/15 pair still covers retained-versus-display scale behavior.','',
            'Extrema gate: retain the strict 1.5-ADC-step diagnostic, but allow provisional conversion when endpoint deviations are within 2% of stored peak-to-peak plus 2 ADC steps. This is explicitly a plausibility allowance for differing frames/overshoot, not a gain correction or an accuracy claim. Old corpus files 4, 10 and 11 still fail.','',
            'Remaining limits: 10X/100X probe factors, other firmware versions/timebases, trigger-relative origin, channel phase/delay, and the three old inconsistent files.']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).parent/'examples/reference')
    parser.add_argument('--out',type=Path,default=Path(__file__).parent/'reference-validation')
    args=parser.parse_args()
    for row in validate(args.source,args.out):print(row)
