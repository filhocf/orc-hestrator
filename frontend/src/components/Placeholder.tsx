interface PlaceholderProps {
  title: string;
}

/** Temporary content for screens not yet implemented. */
export default function Placeholder({ title }: PlaceholderProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <span className="material-symbol text-[48px] text-content-subtle">construction</span>
      <h1 className="font-display text-headline-md text-content">{title}</h1>
      <p className="text-body-md text-content-muted">Tela em breve.</p>
    </div>
  );
}
