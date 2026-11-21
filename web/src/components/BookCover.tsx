import { useState } from 'react';
import { BookOpen } from 'lucide-react';

export function BookCover({ url, title }: { url: string | null; title: string }) {
  const source = url?.trim();
  const [failedSource, setFailedSource] = useState<string>();

  return (
    <div className="book-cover">
      {source && source !== failedSource ? (
        <img src={source} alt={title} onError={() => setFailedSource(source)} />
      ) : (
        <BookOpen size={48} aria-hidden="true" />
      )}
    </div>
  );
}
