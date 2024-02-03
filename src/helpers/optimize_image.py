import logging
from typing import Optional

from PIL import Image
from pytesseract.pytesseract import prepare

import cv2
import numpy as np


def optimize_image(file, optimize=False, output_base: Optional[str] = None):
    input_file_name = f'{file.filename}'
    img_bytes = np.frombuffer(file.read(), dtype='uint8')
    image = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
    initial_brightness = image.mean()

    # Detect white-on-black or dark-mode images
    if initial_brightness < 100:
        # Invert the image (assuming it's originally white-on-black)
        image = cv2.bitwise_not(image)

    if optimize:
        alpha = 1.1  # Controls contrast (1.0 is neutral)
        beta = 0  # Controls brightness (0 is neutral)

        image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
        if output_base:
            cv2.imwrite(f'{output_base}t0_{input_file_name}', image)

        # if initial_brightness < 220:
        #     # lighten very slightly
        #     if initial_brightness < 200:
        #         gamma = 0.98
        #     else:
        #         gamma = 0.99
        #     image = np.uint8(np.power(image / 255.0, gamma) * 255.0)

    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # threshold expects grayscale

    brightness = image.mean()

    # todo: the rect area should be calculated based on the dpi on the input image and maybe font size in segment
    white_balance_darkest = find_darkest_areas(image, rect=3)
    logging.debug(f'brightness {initial_brightness} | {white_balance_darkest} < {brightness} | {(image.shape[0], image.shape[1])} | {input_file_name}')

    # cv2.ADAPTIVE_THRESH_GAUSSIAN_C:
    # - suitable when the document has varying lighting conditions, such as shadows or uneven lighting
    # - can help preserve finer details and text readability, especially for small and bold fonts
    # - due to the Gaussian weighting, tends to provide smoother results
    # cv2.ADAPTIVE_THRESH_MEAN_C:
    # - performs well on documents with uniform lighting
    # - can be effective for normal fonts but may lose some details with bold fonts, especially in the presence of skewed text
    # - can result in sharper transitions between foreground (text) and background.

    # - `binary_method` `threshold` seems to work better for small bold
    # - softer modifications yielded better results for bigger fonts and already good input, cropped to text-boxes (clahe/None)
    # - harder modifications yielded better results for very small fonts or complex/dirty input
    binary_method = 'clahe'  # clahe, bilateral, threshold, None
    binary_dark = 'clahe'  # clahe, bilateral, threshold, clahe+threshold
    if optimize:
        # todo: the letter sparsity should influence the `white_balance_darkest` threshold,
        #       wider letter-spacings but bold text has higher white-balance,
        #       but such dark texts would also benefit for serif or complex fonts
        if white_balance_darkest < 0.086 or brightness < 200:
            logging.debug(f'binary_dark {binary_dark}')
            # assumption: when a small area is dark or in general darker-than-white,
            # the text is most likely a fatter font
            if output_base:
                cv2.imwrite(f'{output_base}t1_{input_file_name}', image)

            # todo: clahe and bilateral should be configured based on the input image dpi
            # todo: also the blockSize of adaptiveThreshold would benefit from letter sizes
            if binary_dark == 'clahe':
                clahe = cv2.createCLAHE(clipLimit=1.4, tileGridSize=(6, 6))
                image = clahe.apply(image)
            elif binary_dark == 'bilateral':
                image = cv2.bilateralFilter(image, d=6, sigmaColor=40, sigmaSpace=60)
            elif binary_dark == 'equalhist':
                # > equalizeHist introduces more artifacts than clahe+threshold on grayish backgrounds
                image = cv2.equalizeHist(image)
                if output_base:
                    cv2.imwrite(f'{output_base}eqh_{input_file_name}', image)
                image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
                # image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            elif binary_dark == 'clahe+threshold':
                # clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(6, 6))
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(6, 6))
                image = clahe.apply(image)
                if output_base:
                    cv2.imwrite(f'{output_base}cl0_{input_file_name}', image)
                # image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
                # THRESH_MEAN seems to work better with preserving details at edges,
                # e.g. § in bigger fonts is mostly detected as 8 with GAUSSIAN (blockSize 11, clip 2.0/tileGrid 6,6 + dilate-erode)
                # > but same result was already "only `equalizeHist`" and better for equalHist + dilate-erode
                image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
                # if white_balance_darkest < 0.042 or brightness < 200:
                #     # for low general white balance, more background focus for more area normalization
                #     # - benefits white-on-dark artifact reduction
                #     image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2.0)
                # else:
                #     # todo: check if used at all and for these if useful
                #     image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 7, 1.97)
            else:
                image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

            if output_base:
                cv2.imwrite(f'{output_base}t2_{input_file_name}', image)

            if binary_dark == 'clahe+threshold' or binary_dark == 'equalhist':
                # dilate+erode only seem to make sense for bigger fonts,
                # needs e.g. min. "char size" to check when to use,
                # maybe also requires config based on the input image dpi
                # seems to be useful to make large bold letters better, together with clahe+threshold
                kernel = np.ones((2, 2), np.uint8)
                dil_image = cv2.dilate(image, kernel, iterations=1)
                er_image = cv2.erode(dil_image, kernel, iterations=1)
                if output_base:
                    cv2.imwrite(f'{output_base}dil_{input_file_name}', dil_image)
                    cv2.imwrite(f'{output_base}er_{input_file_name}', er_image)

                image = er_image
        elif brightness > 231:
            logging.debug(f'binary bright')
            # ~233-237 may be light-typos
            # ~230-233 may be light colors
            # todo: decrease the threshold to ~232 when supporting font-size based conditions
            # todo: this makes very light-typos in light colors in small sizes very bad (equalHist)
            # assumption: very light image suggests very light colored text
            # less likely to cause clipping or over-enhancement of very light grayscale values for low clipLimits
            # assumption: the darker, the more it could be light-typo not light-text
            clahe = cv2.createCLAHE(clipLimit=2.6 if brightness > 238 else 2.4 if brightness > 234 else 2.2, tileGridSize=(4, 4))
            image = clahe.apply(image)
            if output_base:
                cv2.imwrite(f'{output_base}eqh_{input_file_name}', image)
            # gaussian threshold as (maybe small) light text is darkened first to reduce artifacts
            # note: gaussian not helpful for light color+typo
            if brightness > 236:
                # adapt. gauss. blockSize=3 C=1.8 for very small, light color + light typo
                image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 3, 1.85)
            else:
                # adapt. gauss. blockSize=7 C=1.9 for between-small-and-normal, light-to-normal color + normal typo
                # especially lower blockSizes had too many artifacts from clahe
                image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 7, 1.9)
            # image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            # if output_dir:
            #     cv2.imwrite(f'{output_base}eqhtr_{input_file_name}', image)
            # todo: add blur again, only for bigger fonts
            # image = cv2.GaussianBlur(image, (3, 3), 0)  # very slight blur for artifact reduction
        else:
            logging.debug(f'binary_method {binary_method}')
            # todo: clahe and bilateral should be configured based on the input image dpi
            # todo: add here also a clahe+threshold variant
            if binary_method == 'clahe':
                # 4,4 is too small for most title fonts
                clahe = cv2.createCLAHE(clipLimit=2 if brightness > 216 else 1.6, tileGridSize=(6, 6))
                image = clahe.apply(image)
            elif binary_method == 'bilateral':
                image = cv2.bilateralFilter(image, d=4, sigmaColor=40, sigmaSpace=70)
            elif binary_method == 'threshold':
                # todo: try out when found problematic smaller fonts if `ADAPTIVE_THRESH_GAUSSIAN_C` works better in general;
                #       edit: mean seems to make problems with smaller, rather light, skewed texts (but GAUSSIAN is not really better)
                #       edit: but gaussian makes typical scientific fonts very bad it seems
                # image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
                # todo: improve with font size checks, for light-typos (not light colors) not really usable as default
                # `blockSize=5` looks best for small font, but has more artifacts
                # `blockSize=7` looks best for normal font, but has destroys more light-typos
                # image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                # todo: validate that very small clahe appliance with medium grid-size helps the default for light colors/typos
                # clahe = cv2.createCLAHE(clipLimit=1.3, tileGridSize=(6, 6))
                # image = clahe.apply(image)
                # todo: experiment with lower C values as default for lighter/serif texts
                image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 1.9)
                # image = cv2.GaussianBlur(image, (3, 3), 0)  # very slight blur for artifact reduction

    # todo: as come images externally are cropped very near text,
    #       maybe add here a white padding, as now its guaranteed to not influence cutting/coloring
    pil_image = Image.fromarray(image, mode="L")  # L for grayscale

    # applying the default pytesseract image preparation, but storing the image to disk,
    # from disk disables the prep internally and provides batch processing support
    pil_image, extension = prepare(pil_image)
    # todo: multiple files can have the same name
    # todo: the extension must be replaced for certain input files
    if output_base:
        pil_image.save(f'{output_base}{input_file_name}', format=pil_image.format)
    return pil_image


def find_darkest_areas(image, rect=5):
    if len(image.shape) == 3 and image.shape[-1] == 3:
        # RGB image
        height, width, _ = image.shape
    elif len(image.shape) == 2 or (len(image.shape) == 3 and image.shape[-1] == 1):
        # Grayscale image or single-channel image
        height, width = image.shape
    else:
        raise ValueError("Input image must be RGB, grayscale, or single-channel.")

    min_brightness = float('inf')

    for y in range(height - rect - 1):
        for x in range(width - rect - 1):
            if len(image.shape) == 3:
                area = image[y:y + rect, x:x + rect, :]
            else:
                area = image[y:y + rect, x:x + rect]

            brightness = np.mean(area) / 255.0
            if brightness <= 0.01:
                return brightness

            if brightness < min_brightness:
                min_brightness = brightness

    return min_brightness
