import sys
import os
import re

def file_stats(file_ptr):
    counter = {
        k: [] for k in (
            'shoots', 'calibrations', 'loses'
        )
    }
    #print(counter)

    for line in file_ptr.readlines():
        if line.endswith(']\n'):
            timestamp = float(line[(len(line) - line[::-1].find('[')):-2])

            #print(line)
            #print(timestamp)


        ''' '''
        if 'Shoot started' in line:
            counter['shoots'].append({
                'start': timestamp
            })

        elif 'Shoot ended' in line:
            counter['shoots'][-1].update({
                'end': timestamp
            })

        elif 'Calibrating' in line:
            counter['calibrations'].append(timestamp)

        elif 'Lost track' in line:
            counter['loses'].append(timestamp)

        elif 'Ending play after' in line:
            timestamp = float(line[line.find('r')+1:])
            counter['total_time'] = timestamp

    ''' removes shoots without end '''
    counter['shoots'] = list(filter(lambda d: 'end' in d, counter['shoots']))

    return counter

def meta_stats(stats):
    meta = {
        'calibrations': len(stats['calibrations']),
        'loses': len(stats['loses'])
    }

    ''' removes extra shoots '''
    shoots = sorted(stats['shoots'], key = lambda x: x['start'])[:10]

    for shoot in shoots:
        shoot.update({
            'total': shoot['end'] - shoot['start']
        })

    meta.update({
        'shoot_mean_time': sum(map(lambda x: x['total'], shoots)) / len(shoots),
        'total_time': stats['total_time']
    })

    return meta

def main():
    prometido = os.path.join("test_output", "18120218221543782131.test")
    _ = file_stats(open(prometido))
    #print(_)

    for log_file in os.listdir("test_output"):
        log_file = os.path.join("test_output", log_file)
        stats = file_stats(open(log_file))

        performed_shoots = len(stats['shoots'])
        if (performed_shoots in range(10, 12)):
            print(performed_shoots, log_file)

            print(meta_stats(stats))

main() if __name__ == '__main__' else True
