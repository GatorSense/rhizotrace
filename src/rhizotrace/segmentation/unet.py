"""UNet used by the PlantRootSeg P-EnDe model.

Originally by Weihuang Xu (GatorSense, University of Florida), adapted from
https://github.com/GatorSense/PlantRootSeg/blob/master/UNetmodel.py. Included with
permission of the copyright holders (W. Xu and A. Zare). See NOTICE for the citation.

Ronneberger et al. (2015) UNet with padding in every conv (spatial size preserved) and
skip connections that tolerate odd feature-map sizes.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class DownConv(nn.Module):
    def __init__(self, in_channels, out_channels, pooling=True):
        super().__init__()
        self.pooling = pooling
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        skip = x
        if self.pooling:
            pad = 1 if (x.size(2) % 2 == 1 or x.size(3) % 2 == 1) else 0
            x = F.max_pool2d(x, kernel_size=2, stride=2, padding=pad)
        return x, skip


class UpConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.upconv = nn.ConvTranspose2d(in_channels, out_channels, kernel_size=2, stride=2)
        self.conv1 = nn.Conv2d(2 * out_channels, out_channels, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1)

    def forward(self, skip, x):
        x = self.upconv(x)
        x = torch.cat((x[:, :, :skip.size(2), :skip.size(3)], skip), dim=1)
        x = F.relu(self.conv1(x))
        return F.relu(self.conv2(x))


class UNet(nn.Module):
    def __init__(self, num_classes=1, in_channels=3, depth=5, start_filts=64):
        super().__init__()
        down, up = [], []
        out_ch = in_channels
        for i in range(depth):
            in_ch, out_ch = out_ch, start_filts * 2 ** i
            down.append(DownConv(in_ch, out_ch, pooling=i < depth - 1))
        for _ in range(depth - 1):
            in_ch, out_ch = out_ch, out_ch // 2
            up.append(UpConv(in_ch, out_ch))
        self.down_convs = nn.ModuleList(down)
        self.up_convs = nn.ModuleList(up)
        self.conv_final = nn.Conv2d(out_ch, num_classes, kernel_size=1)

    def forward(self, x):
        skips = []
        for module in self.down_convs:
            x, skip = module(x)
            skips.append(skip)
        for i, module in enumerate(self.up_convs):
            x = module(skips[-(i + 2)], x)
        return self.conv_final(x)
