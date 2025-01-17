import numpy as np
from pathlib import Path
import xml.etree.ElementTree as ET
import cv2
import shutil
import collections

def load_func(fpath):
    print('fpath', fpath)
    tree = ET.parse(fpath)
    root = tree.getroot()

    with open(fpath, 'r') as fid:
        lines = fid.readlines()
    records =[json.loads(line.strip('\n')) for line in lines]
    return records

def gen_txt_sets_from_anno(dataset_name, data_root, label_root, train_set = True):
    '''This is a function that read the list of images from label root eand generate all imags path under src/data
        The name of the file will be [dataset_name.train] if 'train_set' is True, otherwise it will be [dataset_name.val]
    '''
    output_path = Path('data')/(dataset_name+'.train') if train_set else Path('data')/(dataset_name+'.val')
    data_root = data_root/'train' if train_set and data_root.name != 'train' else data_root
    data_root = data_root/'test' if not train_set and data_root.name != 'test' else data_root

    with output_path.open('w') as f:
        for sequence_path in label_root.iterdir():
            images_folder_path = Path(data_root.parts[-2], data_root.parts[-1],Path(sequence_path).stem)

            #output_images_path = [str(images_folder_path.parents[2]/x.name.replace('.txt','.jpg')) for x in Path(sequence_path).iterdir()]
            output_images_path = [str(images_folder_path/x.name.replace('.txt','.jpg')) for x in sequence_path.iterdir()]
            f.write('\n'.join(output_images_path))
            f.write('\n')

def gen_labels_uadetrac(data_root, label_root, ann_root, objects_names, keep_no_obj_frame = False, train_set = True):
    '''This is a function that read images (sequences) from data_root and annotation data from ann_root
       The generated label data (given in the path label_root) in txt files are the one used for train.py
       TODO: there is no object type from groundtruth written to labels_with_ids txt. Should has this option in the future
    '''
    label_root.mkdir(parents = True, exist_ok = True)
    data_root = data_root/'train' if train_set and data_root.name != 'train' else data_root
    data_root = data_root/'test' if not train_set and data_root.name != 'test' else data_root

    if not data_root.exists():
        data_root.mkdir(parents = True)
        for sequence_path in data_root.parents[0].iterdir():
            if train_set and sequence_path.name != 'train':
                images_folder_path = shutil.move(str(sequence_path), str(images_folder_path.parents[0]/'train'))
            if not train_set and sequence_path.name != 'test':
                images_folder_path = shutil.move(str(sequence_path), str(images_folder_path.parents[0]/'test'))
      

    # clear label txt files before append 
    for label_file in label_root.glob('**/**/*.txt'):
        label_file.unlink()
    
    for sequence_path in ann_root.iterdir():
        #if sequence_path.stem == 'MVI_39811':
        seq_imgs_path = data_root/sequence_path.stem
        # get the length of the video
        total_frames = collections.Counter(p.suffix for p in seq_imgs_path.iterdir())['.jpg']

        print('Processing sequence:{}, total frames:{}'.format(sequence_path.name, total_frames))
        tree = ET.parse(sequence_path)
        root = tree.getroot()
        frame_index_counter = 0
        for ann_data in root.iter():     
            if ann_data.tag == 'frame':
                frame_index_counter += 1 
                fid = int(ann_data.attrib['num']) # ID of frame in this sequence
                num_objects = int(ann_data.attrib['density'])

                # No object detected in these previous frames, create empty txt files
                if keep_no_obj_frame:
                    while frame_index_counter < fid:
                        image_name = 'img{0:05d}.jpg'.format(frame_index_counter)
                        img_path = data_root/sequence_path.stem/image_name
                        if img_path.exists():
                            label_fpath = (label_root/sequence_path.stem/image_name).with_suffix('.txt')
                        else:
                            print('Warning! Missed frame image {}'.format(frame_index_counter))
                        open(label_fpath,'w').close()
                        frame_index_counter +=1

                image_name = 'img{0:05d}.jpg'.format(fid)
                #print(i)
                #anns_data = load_func(ann_root)
                #image_name = '{}.jpg'.format(ann_data['ID'])
                img_path = data_root/sequence_path.stem/image_name             
                img = cv2.imread(
                    str(img_path),
                    cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION
                )
                img_height, img_width = img.shape[0:2]

                label_fpath = (label_root/sequence_path.stem/image_name).with_suffix('.txt')
                if not label_fpath.parents[0].exists():
                    label_fpath.parents[0].mkdir(parents=True)
                
                with label_fpath.open('w') as f:
                    tid_curr = 0
                    for target in list(ann_data[0]):
                        tid = int(target.attrib['id'])

                        anns = target[0].attrib
                        # Control target objects by the conditions provided in target[1].attrib
                        # There are {orientation, speed, trajectory_length', 'truncation_ratio', 'vehicle_type'}
                        if target[1].attrib['vehicle_type'] not in objects_names:
                            print('Error that target object is not in provided class name list !')
                            break

                        x, y, w, h = float(anns['left']), float(anns['top']), float(anns['width']), float(anns['height'])
                        x += w / 2
                        y += h / 2
                        # Expected format: class id x_center/img_width y_center/img_height w/img_width h/img_height

                        # every objects as one class code
                        label_str = '0 {:d} {:.6f} {:.6f} {:.6f} {:.6f}\n'.format(
                           tid, x / img_width, y / img_height, w / img_width, h / img_height)
                        
                        # # With the multiple classes TODO: use this code when we solve limitation in JointDataset that assign num_classes = 1
                        # label_str = '{:d} {:d} {:.6f} {:.6f} {:.6f} {:.6f}\n'.format(objects_names.index(target[1].attrib['vehicle_type']),
                        #     tid, x / img_width, y / img_height, w / img_width, h / img_height)

                        f.write(label_str)

        if keep_no_obj_frame:
            while frame_index_counter <= total_frames:
                # make sure all the images files has the anno txt even if there is no detected objects
                image_name = 'img{0:05d}.jpg'.format(frame_index_counter)
                label_fpath = (label_root/sequence_path.stem/image_name).with_suffix('.txt')
                if not label_fpath.parents[0].exists():
                    label_fpath.parents[0].mkdir(parents=True)
                open(label_fpath,'w').close()
                frame_index_counter +=1
        # Generate list of images path for training (*.train) or for validation (*.val)
        



if __name__ == '__main__':
    dataset_name = 'UA-DETRAC_small'
    root_path = Path('../../MOT_data/UA-DETRAC_small')

    # dataset_name = 'UA-DETRAC'
    # root_path = Path('../../MOT_data/UA-DETRAC')

    path_images = root_path/'images'
    
    label_train = root_path/'labels_with_ids/train'
    ann_train = root_path / 'DETRAC-Train-Annotations-XML'

    label_val = root_path/'labels_with_ids/val'
    ann_val = root_path / 'DETRAC-Test-Annotations-XML'

    # New classes name for CVAT label.txt
    objects_names = list(('car', 'bus', 'van','others'))
    cvat_label_path = root_path/'for_cvat'/'labels.txt'
    if not cvat_label_path.parents[0].exists():
        cvat_label_path.parents[0].mkdir(parents=True)

    with cvat_label_path.open('w') as out_txt_file:
        for i in objects_names:
            print(i, file =out_txt_file )
    
    gen_labels_uadetrac(path_images, label_train, ann_train, objects_names, train_set = True)
    gen_labels_uadetrac(path_images, label_val, ann_val,objects_names, train_set = False)
    gen_txt_sets_from_anno(dataset_name, path_images, label_train, train_set = True)
    gen_txt_sets_from_anno(dataset_name, path_images, label_val, train_set = False)
