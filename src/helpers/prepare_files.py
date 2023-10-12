import random
import string

from helpers.optimize_image import optimize_image


def prepare_files(files, optimize=False, save_intermediate=False):
    infer_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    paths = []
    for i, file in enumerate(files):
        input_file_name = f'{file.filename}'
        pil_image = optimize_image(file, optimize, f'/app/shared-assets/{infer_id}_{i}_' if save_intermediate else None)
        # todo: the extension must be replaced for certain input files
        if save_intermediate:
            pil_image.save(f'/app/shared-assets/{infer_id}_{i}_{input_file_name}', format=pil_image.format)
        pil_image.save(f'/tmp/{infer_id}_{i}_{input_file_name}', format=pil_image.format)
        paths.append(f'/tmp/{infer_id}_{i}_{input_file_name}')

    if len(paths) == 1:
        # when only a single path, no batch processing needed
        return paths, paths[0], infer_id

    # creating a text file with all files for batching
    with open(f'/tmp/{infer_id}.txt', "w") as file:
        file.write('\n'.join(paths))

    return paths, f'/tmp/{infer_id}.txt', infer_id
