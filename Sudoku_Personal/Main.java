import java.util.Scanner;

//PROGRAMA PARA INTRODUCIR Y RESOLVER SUDOKUS

public class Main {
    public static void main(String[] args) {

        Scanner teclado = new Scanner(System.in);

        boolean correcto = true; //Booleano para determinar si se debe corregir algún valor
        char respuesta = 'x';
        int input = -1;
        int [][] sudoku = {{0, 0, 0, 0, 0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0, 0, 0, 0, 0}};

        System.out.println("El siguiente programa resuelve sudokus que reciba por el teclado");
        System.out.println("Las casillas en blanco es escriben como un cero (0)");
        System.out.println("----------------------------------------------------------------");

        for (int i = 0; i < 9; i++){
            switch (i) {
                case 0:
                    System.out.println("Por favor introduce los números de la primera fila:");
                    break;
                case 1:
                    System.out.println("Por favor introduce los números de la segunda fila:");
                    break;
                case 2:
                    System.out.println("Por favor introduce los números de la tercera fila:");
                    break;
                case 3:
                    System.out.println("Por favor introduce los números de la cuarta fila:");
                    break;
                case 4:
                    System.out.println("Por favor introduce los números de la quinta fila:");
                    break;
                case 5:
                    System.out.println("Por favor introduce los números de la sexta fila:");
                    break;
                case 6:
                    System.out.println("Por favor introduce los números de la séptima fila:");
                    break;
                case 7:
                    System.out.println("Por favor introduce los números de la octava fila:");
                    break;
                case 8:
                    System.out.println("Por favor introduce los números de la novena fila:");
                    break;
            }
            for (int j = 0; j < 9; j++){ //Se llena toda la fila
                System.out.print("Celda #" + (j+1) + ": ");
                sudoku[i][j] = Sudoku.insertar(teclado);
            }
            System.out.println("¿La fila actual es correcta? S/N");
            Matriz.printValores(sudoku);
            do{
                respuesta = teclado.next().charAt(0);
                if (respuesta == 'n' || respuesta == 'N'){
                    System.out.println("¿Cuál celda se debe modificar?");
                    input = (teclado.nextInt() - 1);
                    System.out.print("Celda #" + (input + 1) + ": ");
                    sudoku[i][input] = Sudoku.insertar(teclado);
                    System.out.println("¿La fila actual es correcta? S/N");
                    Matriz.printValores(sudoku);
                }
            } while (respuesta != 's' && respuesta != 'S'); //Sólo continúa a la siguiente fila cuando no hay errores

            respuesta = 'x'; //Reiniciando valor de respuesta
        }

        int N = sudoku.length;
        boolean[][] visitados = new boolean [N][N];

        System.out.println("La solución del sudoku es la siguiente:");
        Sudoku.solucion(sudoku, visitados);
    }
}
