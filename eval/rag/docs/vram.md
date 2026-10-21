GPU memory budget

The card has 16 GB of VRAM. An 8B model at 16k context uses about 7 GB and a
14B model about 11 GB. Weights plus KV cache plus 1 GB of headroom must stay
under roughly 14.5 GB, so a 30B model does not fit.
