"""CSS styles for the web application."""

CSS_STYLES = """
body { font-family: system-ui, -apple-system, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
.container { background: #f5f5f5; padding: 2rem; border-radius: 8px; margin: 1rem 0; }
.file-info { background: white; padding: 1rem; margin: 1rem 0; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.operation-buttons { display: flex; gap: 10px; flex-wrap: wrap; margin: 1rem 0; }
.operation-buttons button { flex: 1; min-width: 150px; }
button, .button {
    background-color: #007bff;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    font-size: 14px;
    transition: background-color 0.3s;
}
button:hover, .button:hover {
    background-color: #0056b3;
}
button:active, .button:active {
    transform: translateY(1px);
}
.result-area { background: white; padding: 1.5rem; margin: 1rem 0; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.error { color: #dc3545; padding: 1rem; background: #f8d7da; border-radius: 4px; margin: 1rem 0; }
.success { color: #155724; padding: 1rem; background: #d4edda; border-radius: 4px; margin: 1rem 0; }
.warning { color: #856404; padding: 1rem; background: #fff3cd; border-radius: 4px; margin: 1rem 0; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }
th { background-color: #f2f2f2; font-weight: bold; }
tbody tr:hover { background-color: #f5f5f5; }
.toc-level-0 { font-weight: bold; }
.toc-level-1 { padding-left: 20px; }
.toc-level-2 { padding-left: 40px; }
.toc-level-3 { padding-left: 60px; }
.image-gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
.image-thumb { max-width: 100%; height: auto; border: 1px solid #ddd; }
.loading { opacity: 0.6; pointer-events: none; }
.spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(0,0,0,.1); border-radius: 50%; border-top-color: #007bff; animation: spin 1s ease-in-out infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.image-extraction-grid { 
    display: grid; 
    grid-template-columns: repeat(4, 1fr); 
    gap: 15px; 
    margin-bottom: 20px;
}
@media (max-width: 1200px) {
    .image-extraction-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 900px) {
    .image-extraction-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
    .image-extraction-grid { grid-template-columns: 1fr; }
}
.image-thumbnail {
    width: 100%;
    height: 300px;
    object-fit: contain;
    border: 1px solid #ddd;
    background: #f9f9f9;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}
.image-thumbnail:hover {
    transform: scale(1.02);
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}
.image-item {
    display: flex;
    justify-content: center;
    align-items: center;
    background: white;
    border-radius: 4px;
    overflow: hidden;
}
.page-separator {
    grid-column: 1 / -1;
    margin: 20px 0 10px 0;
    padding-top: 20px;
    border-top: 2px solid #e0e0e0;
}
.page-separator:first-child {
    border-top: none;
    padding-top: 0;
}
.image-gallery-container {
    max-height: 800px;
    overflow-y: auto;
    padding: 10px;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background: #fafafa;
}
"""