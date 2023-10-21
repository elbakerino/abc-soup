import logging
from typing import List

from werkzeug.datastructures import FileStorage

convert = {
    'level': int,
    'page_num': int,
    'block_num': int,
    'par_num': int,
    'line_num': int,
    'word_num': int,
    'left': int,
    'top': int,
    'width': int,
    'height': int,
    'conf': float,
}


def process_data(
    files: List[FileStorage],
    tsv: str,
    intra_block_breaks=True,  # adds line breaks when text is below each other
    keep_details=False,
):
    # todo: reduce loops
    columns = []
    pages = []
    page_data = None
    block_data = None
    for i, line in enumerate(tsv.split('\n')):
        if i == 0:
            for j, column in enumerate(line.split('\t')):
                columns.append(column)
            continue

        row_data = {}
        for j, value in enumerate(line.split('\t')):
            column = columns[j]
            if column in convert:
                if value == '':
                    value = None
                else:
                    value = convert[column](value)
            row_data[column] = value

        if 'page_num' not in row_data:
            if 'level' in row_data and row_data['level'] is None:
                # somehow always a row with just `level: None` exists
                continue
            logging.info(f'invalid row-data {row_data}')
            continue

        if row_data['conf'] < 1:
            # low confidence score
            continue
        if not page_data or page_data['page'] != row_data['page_num']:
            # separating data for different files (e.g. batch mode)
            page_data = {
                'page': row_data['page_num'],
                'file': files[len(pages)].filename,
                'blocks': [],
            }
            pages.append(page_data)
            block_data = None
        if not block_data or block_data['block'] != row_data['block_num']:
            block_data = {
                'block': row_data['block_num'],
                'text': '',
                'boxes': [],
            }
            page_data['blocks'].append(block_data)

        block_data['boxes'].append(row_data)

    for page in pages:
        blocks_copy = page['blocks'].copy()  # copy to filter in next loop
        del page['blocks']
        content = []
        blocks = []
        for block in blocks_copy:
            last_box_y2 = None
            for box in block['boxes']:
                if intra_block_breaks and last_box_y2 and last_box_y2 < box['top']:
                    # previous box is above current one
                    block['text'] += '\n'
                else:
                    block['text'] += ' '
                block['text'] += box['text']
                last_box_y2 = box['top'] + box['height']

            block['text'] = block['text'].strip()
            if block['text'] == '':
                # ignoring "empty text" blocks (NOT boxes)
                continue
            content.append(block['text'])
            blocks.append(block)

        if keep_details:
            page['blocks'] = blocks
        else:
            page['content'] = '\n\n'.join(content)

    return pages
