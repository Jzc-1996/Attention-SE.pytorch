import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class AttentionModel(nn.Module):
    def __init__(self, input_size, hidden_size, stacked_encoder=False, use_attn=True, attn_len=0):
        # attn_len 0 for full attention(Causal Dynamic Attention),
        # Else x_t-w, ..., x_t only used(Causeal Local Attention).
        super(AttentionModel, self).__init__()
        self.stacked_encoder = stacked_encoder if use_attn else True
        self.use_attn = use_attn
        self.attn_len = attn_len

        self.feat = nn.Linear(input_size, hidden_size)
        self.k_enc = nn.LSTM(hidden_size, hidden_size)
        self.q_enc = nn.LSTM(hidden_size, hidden_size)

        # TODO - Dropout
        self.score = nn.Linear(hidden_size, hidden_size, bias=False)

        enhance_in = hidden_size * (2 if use_attn else 1)
        self.enhance = nn.Linear(enhance_in, hidden_size)
        self.mask = nn.Linear(hidden_size, input_size)

    def forward(self, x):
        # x dim (B, T, F)
        input_x = x
        # TODO - Put dropout somewhere

        # Encoder
        x = self.feat(x)
        k, _ = self.k_enc(x)
        q, _ = self.q_enc(k if self.stacked_encoder else x)

        # Attention
        out = q
        if self.use_attn:
            # attn_score dim (B x T x T'(k))
            attn_score = torch.bmm(self.score(q), k.transpose(1, 2))
            exp_score = torch.exp(attn_score)

            # Causal contraints(score <= t)
            attn_weights = torch.tril(exp_score)
            if self.attn_len > 0:
                # Static constraints(t - w <= score)
                attn_weights = torch.triu(attn_weights, diagonal=-self.attn_len)
            weights_denom = torch.sum(attn_weights, dim=-1, keepdim=True)
            attn_weights = attn_weights / (weights_denom + 1e-10)

            c = torch.bmm(attn_weights, k)

            # concat query and context
            out = torch.cat((c, q), -1)

        # Generator
        out = self.enhance(out).tanh()
        out = self.mask(out).sigmoid()

        return input_x * out, attn_weights