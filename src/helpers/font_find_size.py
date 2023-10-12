import cv2


def find_single_letter_sizes(image, min_area, max_area):
    # todo: this fn should find sizes of letters by contour boxes,
    #       but mostly detects the whole text area instead of single letters
    alpha = 0.8  # Controls contrast (1.0 is neutral)
    beta = 0  # Controls brightness (0 is neutral)
    image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
    image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 7, 2)

    # Find contours in the binary image
    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    potential_sizes = []

    for contour in contours:
        # Calculate the area of the contour
        area = cv2.contourArea(contour)

        # Get the bounding box of the contour
        x, y, w, h = cv2.boundingRect(contour)
        print(f'contour: {area} | {w} {h}')

        # Check if the area of the contour is within the specified range
        if min_area <= area <= max_area:
            potential_sizes.append((w, h))

    return potential_sizes
