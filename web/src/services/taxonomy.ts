import taxonomy from '../../../data/taxonomy.json';

export function genreLabel(code: string): string {
  return taxonomy.genres.find(item => item.code === code)?.label ?? code;
}

export function topicLabel(code: string): string {
  return taxonomy.topics.find(item => item.code === code)?.label ?? code;
}
