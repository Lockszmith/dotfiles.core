return {
  'andre-kotake/nvim-chezmoi',
  lazy = false,
  dependencies = {
    { 'nvim-lua/plenary.nvim' },
  },
  opts = {},
  config = function(_, opts)
    require('nvim-chezmoi').setup(opts)
  end,
}
