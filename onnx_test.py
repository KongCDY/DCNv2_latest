import math
import torch
import torch.nn as nn
from torch.nn.modules.utils import _pair
torch.ops.load_library('_ext.cpython-37m-x86_64-linux-gnu.so')

def register_custom_op():
    def my_dcn_forward(g, input, weight, bias, offset, mask, kernel_h, kernel_w, stride_h, stride_w, padding_h, padding_w, dilation_h, dilation_w, deformable_groups):
        return g.op("mydomain::testdcn", input, weight, bias, offset, mask, kernel_h, kernel_w, stride_h, stride_w, padding_h, padding_w, dilation_h, dilation_w, deformable_groups)

    from torch.onnx import register_custom_op_symbolic

    register_custom_op_symbolic("mynamespace::dcn_v2_forward", my_dcn_forward, 9)

class DCNv2_ONNX(nn.Module):
    def __init__(
        self,
        in_channels,
        out_channels,
        kernel_size,
        stride = 1,
        padding = 0,
        dilation=1,
        deformable_groups=1,
    ):
        super(DCNv2_ONNX, self).__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = _pair(kernel_size)
        self.stride = _pair(stride)
        self.padding = _pair(padding)
        self.dilation = _pair(dilation)
        self.deformable_groups = deformable_groups

        self.weight = nn.Parameter(torch.Tensor(out_channels, in_channels, *self.kernel_size))
        self.bias = nn.Parameter(torch.Tensor(out_channels))
        self.reset_parameters()

    def reset_parameters(self):
        n = self.in_channels
        for k in self.kernel_size:
            n *= k
        stdv = 1.0 / math.sqrt(n)
        self.weight.data.uniform_(-stdv, stdv)
        self.bias.data.zero_()

    def forward(self, input, offset, mask):
        assert (
            2 * self.deformable_groups * self.kernel_size[0] * self.kernel_size[1]
            == offset.shape[1]
        )
        assert self.deformable_groups * self.kernel_size[0] * self.kernel_size[1] == mask.shape[1]
        return torch.ops.mynamespace.dcn_v2_forward(
            input,
            self.weight,
            self.bias,
            offset,
            mask,
            torch.Tensor([self.kernel_size[0]]),
            torch.Tensor([self.kernel_size[1]]),
            torch.Tensor([self.stride[0]]),
            torch.Tensor([self.stride[1]]),
            torch.Tensor([self.padding[0]]),
            torch.Tensor([self.padding[1]]),
            torch.Tensor([self.dilation[0]]),
            torch.Tensor([self.dilation[1]]),
            torch.Tensor([self.deformable_groups]),
        )

def export_custom_op():
    deformable_groups = 1
    N, inC, inH, inW = 2, 2, 4, 4
    outC = 2
    kH, kW = 3, 3

    model = DCNv2_ONNX(inC, outC, (kH, kW), padding = 1)
    input = torch.rand(N, inC, inH, inW) * 0.01
    offset = torch.randn(N, deformable_groups * 2 * kW * kH, inH, inW) * 2
    mask = torch.rand(N, deformable_groups * 1 * kW * kH, inH, inW)
    mask = torch.sigmoid(mask)
    inputs = (input, offset, mask)

    f = './model.onnx'
    torch.onnx.export(model, inputs, f,
                      opset_version=9,
                      example_outputs=None,
                      custom_opsets={"mydomain": 1})

register_custom_op()
export_custom_op()
print('export onnx')
