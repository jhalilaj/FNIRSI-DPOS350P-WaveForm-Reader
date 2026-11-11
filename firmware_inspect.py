"""Read-only firmware package inventory; never flashes or executes the image."""
import argparse,hashlib,json,struct
from pathlib import Path


def inspect(data):
    if not data.startswith(b'DPOS350P'):
        raise ValueError('Unrecognized package signature')
    result={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'package_signature':'DPOS350P','parts':[],'executed':False}
    for marker in (b'eGON.BMP',b'eGON.EXE'):
        at=data.find(marker)
        if at<4 or at+16>len(data):continue
        start=at-4
        size=struct.unpack_from('<I',data,start+16)[0]
        result['parts'].append({'signature':marker.decode(),'header_offset':start,
                                'declared_bytes':size,'fits_in_file':start+size<=len(data),
                                'payload_offset_candidate':start+32})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    try:result=inspect(args.firmware.read_bytes())
    except (OSError,ValueError) as exc:parser.exit(2,str(exc)+'\n')
    text=json.dumps(result,indent=2)
    if args.out:args.out.write_text(text,encoding='utf-8')
    print(text)
