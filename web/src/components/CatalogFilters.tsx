import { useState } from 'react';
import type { FacetsResponse, Filters } from '../types/api';
import { Button, Input } from './ui';

function Choices({ name, options, selected, onChange }: {
  name: string;
  options: { code: string; label: string }[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const [query, setQuery] = useState('');
  return <fieldset>
    <legend>{name}</legend>
    <Input id={name === 'Tác giả' ? 'catalog-author' : 'catalog-genre'} label={`Tìm ${name.toLowerCase()}`}
      value={query} onChange={event => setQuery(event.target.value)} />
    <div className="catalog-choices">
      {options.filter(option => option.label.toLocaleLowerCase('vi').includes(query.trim().toLocaleLowerCase('vi')))
        .map(({ code, label }) => <label key={code}>
          <input type="checkbox" checked={selected.includes(code)}
            onChange={event => onChange(event.target.checked ? [...selected, code] : selected.filter(value => value !== code))} />
          {label}
        </label>)}
    </div>
  </fieldset>;
}

export function CatalogFilters({ facets, value, onChange, onApply, onClear, pending }: {
  facets: FacetsResponse | null;
  value: Filters;
  onChange: (value: Filters) => void;
  onApply: () => void;
  onClear: () => void;
  pending: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  return <aside className="catalog-filters card" aria-label="Bộ lọc danh mục">
    <Button className="catalog-filter-toggle" variant="outline" aria-controls="catalog-filter-form"
      aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>Bộ lọc</Button>
    <form id="catalog-filter-form" className={expanded ? 'catalog-filter-form expanded' : 'catalog-filter-form'}
      onSubmit={event => { event.preventDefault(); onApply(); }}>
      <Choices name="Tác giả" options={facets?.authors.map(author => ({ code: author, label: author })) ?? []}
        selected={value.authors ?? []} onChange={authors => onChange({ ...value, authors })} />
      <Choices name="Thể loại" options={facets?.genres ?? []} selected={value.genres ?? []}
        onChange={genres => onChange({ ...value, genres })} />
      <label className="filter-check"><input type="checkbox" checked={value.has_fulltext === true}
        onChange={event => onChange({ ...value, has_fulltext: event.target.checked || undefined })} />Chỉ sách có toàn văn</label>
      <Button type="submit" disabled={pending}>Áp dụng bộ lọc</Button>
      <Button variant="outline" onClick={onClear}>Xóa bộ lọc</Button>
    </form>
  </aside>;
}
