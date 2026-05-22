# Data Credits & Attribution

This project uses the following external datasets for seeding realistic fragment data.

## Free Music Archive (FMA)

Audio metadata (track titles, genres, BPM, key, energy, danceability, etc.)

- **Repository**: https://github.com/mdeff/fma
- **Paper**: Defferrard, M., Benzi, K., Vandergheynst, P., & Bresson, X. (2017). FMA: A Dataset for Music Analysis. *ISMIR 2017*.
- **arXiv**: https://arxiv.org/abs/1612.01840
- **License**: Audio tracks are individually licensed by their artists (Creative Commons). Metadata is provided for research purposes.
- **Usage in this project**: We use only the metadata (tracks.csv, echonest.csv) — no audio files are downloaded or distributed.

## LabROSA Lyric Database (LYRICAL)

Lyrics with structural annotations (verse, chorus, bridge, etc.)

- **Repository**: https://github.com/mattmcvicar/lyric_database
- **Authors**: Matt McVicar, LabROSA (Columbia University)
- **Paper**: McVicar, M., et al. (2014). Automatic Retrieval of Music Lyrics. *Foundations and Trends in Information Retrieval*.
- **Usage in this project**: We parse structure-annotated lyrics to create text-type fragment entries. No audio is used.

## Citation

If you use or reference the seed data in this project, please cite the original authors:

```bibtex
@inproceedings{fma_dataset,
  title  = {FMA: A Dataset for Music Analysis},
  author = {Defferrard, Micha{\"e}l and Benzi, Kirell and Vandergheynst, Pierre and Bresson, Xavier},
  year   = {2017},
  booktitle = {18th International Society for Music Information Retrieval Conference (ISMIR)},
}

@article{mcvicar2014lyrics,
  title   = {Automatic Retrieval of Music Lyrics},
  author  = {McVicar, Matt and others},
  journal = {Foundations and Trends in Information Retrieval},
  year    = {2014},
}
```
