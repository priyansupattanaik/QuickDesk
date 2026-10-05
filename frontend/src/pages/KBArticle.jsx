import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import client from "../api/client";

export default function KBArticle() {
  const { id } = useParams();
  const [article, setArticle] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    client.get(`/api/kb/articles/${id}`)
      .then(({ data }) => setArticle(data))
      .catch((err) => setError(err.response?.data?.detail || "Unable to load knowledge-base article"));
  }, [id]);

  if (error) {
    return <section className="page-container"><div className="form-error" role="alert">{error}</div><Link to="/dashboard" className="back-link"><ArrowLeft size={16} /> Back to queue</Link></section>;
  }
  if (!article) return <div className="loading-state">Loading source article...</div>;

  return (
    <section className="page-container article-page">
      <Link to="/dashboard" className="back-link"><ArrowLeft size={16} /> Back to queue</Link>
      <div className="article-shell">
        <div className="article-kicker">Verified knowledge-base source</div>
        <h1 className="page-title">{article.title}</h1>
        <p className="article-slug">Source: {article.slug}</p>
        <article className="article-content" aria-label="Knowledge-base article content">
          {article.content}
        </article>
      </div>
    </section>
  );
}
