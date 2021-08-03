import glob
import os
import csv
import numpy as np
import scipy.io

# from .lsd import lsd


def rgb2gray(rgb):
    return np.dot(rgb[..., :3], [0.2989, 0.5870, 0.1140])


class NYUVP:
    def __init__(
        self,
        data_dir_path="./data",
        keep_data_in_memory=True,
        mat_file_path=None,
        remove_borders=True,
    ):
        """
        NYU-VP dataset class
        :param data_dir_path: Path where the CSV files containing VP labels etc. are stored
        :param split: train, val, test, trainval or all
        :param keep_data_in_memory: whether data shall be cached in memory
        :param mat_file_path: path to the MAT file containing the original NYUv2 dataset
        :param normalise_coordinates: normalise all point coordinates to a range of (-1,1)
        :param remove_borders: ignore the white borders around the NYU images
        :param extract_lines: do not use the pre-extracted line segments
        """
        self.keep_in_mem = keep_data_in_memory
        self.remove_borders = remove_borders

        self.vps_files = glob.glob(os.path.join(data_dir_path, "vps*"))
        self.labelled_line_files = glob.glob(
            os.path.join(data_dir_path, "labelled_lines*"))
        self.vps_files.sort()
        self.labelled_line_files.sort()

        self.set_ids = list(range(0, 1449))

        self.dataset: list = [None for _ in self.set_ids]

        self.data_mat = None
        if mat_file_path is not None:
            self.data_mat = scipy.io.loadmat(
                mat_file_path, variable_names=["images", "depths"])

        fx_rgb = 5.1885790117450188e02
        fy_rgb = 5.1946961112127485e02
        cx_rgb = 3.2558244941119034e02
        cy_rgb = 2.5373616633400465e02

        K = np.matrix([[fx_rgb, 0, cx_rgb], [0, fy_rgb, cy_rgb], [0, 0, 1]])

        self.Kinv = K.I

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, key):
        """
        Returns a sample from the dataset.
        :param key: image ID within the selected dataset split
        :return: dictionary containing vanishing points, line segments, original image
        """
        id = self.set_ids[key]

        datum = self.dataset[key]

        if datum is None:
            if self.data_mat is not None:
                image_rgb = (self.data_mat["images"][:, :, :,
                                                     id]).astype(np.float32)
            else:
                image_rgb = None

            labelled_line_segments = []
            with open(self.labelled_line_files[id], "r") as csv_file:
                reader = csv.DictReader(csv_file, delimiter=" ")
                for line in reader:
                    lines_per_vp = []
                    for i in range(1, 5):
                        key_x1 = "line%d_x1" % i
                        key_y1 = "line%d_y1" % i
                        key_x2 = "line%d_x2" % i
                        key_y2 = "line%d_y2" % i

                        if line[key_x1] == "":
                            break

                        p1x = float(line[key_x1])
                        p1y = float(line[key_y1])
                        p2x = float(line[key_x2])
                        if line[key_y2] == "433q":
                            assert False, self.labelled_line_files[id]
                        p2y = float(line[key_y2])

                        ls = np.array([p1x, p1y, p2x, p2y])
                        lines_per_vp += []
                        lines_per_vp += [ls]
                    lines_per_vp = np.vstack(lines_per_vp)
                    labelled_line_segments += [lines_per_vp]

            vp_list = []
            vd_list = []
            with open(self.vps_files[id]) as csv_file:
                reader = csv.reader(csv_file, delimiter=" ")
                for ri, row in enumerate(reader):
                    if ri == 0:
                        continue
                    vp = np.array([
                        float(row[1]),
                        float(row[2]),
                        1,
                    ])
                    vp_list += [vp]

                    vd = np.array(self.Kinv @ np.matrix(vp).T)
                    vd /= np.linalg.norm(vd)
                    vd_list += [vd]
            vps = np.vstack(vp_list)
            vds = np.vstack(vd_list).reshape(-1, 3)

            depth = None
            if self.data_mat is not None:
                depth = np.expand_dims(self.data_mat["depths"][..., id],
                                       axis=2)

            datum = {
                "VPs": vps,
                "id": id,
                "VDs": vds,
                "image": image_rgb,
                "labelled_lines": labelled_line_segments,
                "depth": depth
            }

            for vi in range(datum["VPs"].shape[0]):
                datum["VPs"][vi, :] /= np.linalg.norm(datum["VPs"][vi, :])

            if self.keep_in_mem:
                self.dataset[key] = datum

        return datum


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import argparse

    parser = argparse.ArgumentParser(
        description="NYU-VP dataset visualisation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--mat_file", default=None, help="Dataset directory")
    opt = parser.parse_args()
    mat_file_path = opt.mat_file

    if mat_file_path is None:
        print(
            "Specify the path where your 'nyu_depth_v2_labeled.mat' " +
            "is stored using the --mat_file option in order to load the original RGB images."
        )

    dataset = NYUVP(
        "./data",
        mat_file_path=mat_file_path,
        remove_borders=True,
    )

    show_plots = True

    max_num_vp = 0
    all_num_vps = []

    for idx in range(len(dataset)):
        vps = dataset[idx]["VPs"]
        num_vps = vps.shape[0]
        print("image no. %04d -- vps: %d" % (idx, num_vps))
        all_num_vps += [num_vps]
        if num_vps > max_num_vp:
            max_num_vp = num_vps

        ls = dataset[idx]["line_segments"]
        vp = dataset[idx]["VPs"]

        if show_plots:
            image = dataset[idx]["image"]
            ls_per_vp = dataset[idx]["labelled_lines"]

            colours = [
                "#e6194b",
                "#4363d8",
                "#aaffc3",
                "#911eb4",
                "#46f0f0",
                "#f58231",
                "#3cb44b",
                "#f032e6",
                "#008080",
                "#bcf60c",
                "#fabebe",
                "#e6beff",
                "#9a6324",
                "#fffac8",
                "#800000",
                "#aaffc3",
                "#808000",
                "#ffd8b1",
                "#000075",
                "#808080",
                "#ffffff",
                "#000000",
            ]

            fig = plt.figure(figsize=(16, 5))
            ax1 = plt.subplot2grid((1, 3), (0, 0))
            ax2 = plt.subplot2grid((1, 3), (0, 1))
            ax3 = plt.subplot2grid((1, 3), (0, 2))
            ax1.set_aspect("equal", "box")
            ax2.set_aspect("equal", "box")
            ax3.set_aspect("equal", "box")
            ax1.axis("off")
            ax2.axis("off")
            ax3.axis("off")
            ax1.set_title("original image")
            ax2.set_title("labelled line segments per VP")
            ax3.set_title("extracted line segments")

            if image is not None:
                ax1.imshow(image)
                ax2.imshow(rgb2gray(image), cmap="Greys_r")
            else:
                ax1.text(
                    0.5,
                    0.5,
                    "not loaded",
                    horizontalalignment="center",
                    verticalalignment="center",
                    transform=ax1.transAxes,
                    fontsize=12,
                    fontweight="bold",
                )

            for vpidx, lss in enumerate(ls_per_vp):
                c = colours[vpidx]
                for l in lss:
                    if image is None:
                        l[1] *= -1
                        l[3] *= -1
                    ax2.plot([l[0], l[2]], [l[1], l[3]], "-", c=c, lw=5)
            for li in range(ls.shape[0]):
                ax3.plot([ls[li, 0], ls[li, 3]], [-ls[li, 1], -ls[li, 4]],
                         "k-",
                         lw=2)

            fig.tight_layout()
            plt.show()

    print(
        "num VPs: ",
        np.sum(all_num_vps),
        np.sum(all_num_vps) * 1.0 / len(dataset),
        np.max(all_num_vps),
    )

    plt.rcParams.update({"font.size": 18})
    plt.figure(figsize=(9, 3))
    values, bins, patches = plt.hist(
        all_num_vps, bins=[0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5])
    print(values)
    print(bins)
    plt.show()
